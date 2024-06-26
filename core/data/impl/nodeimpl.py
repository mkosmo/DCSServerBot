import aiofiles
import aiohttp
import asyncio
import certifi
import discord
import gzip
import json
import logging
import os
import platform
import psycopg
import re
import shutil
import ssl
import subprocess
import sys
import time

from collections import defaultdict
from contextlib import closing
from core import utils, Status, Coalition
from core.const import SAVED_GAMES
from core.translations import get_translation
from core.utils.os import CloudRotatingFileHandler
from discord.ext import tasks
from packaging import version
from pathlib import Path
from psycopg.errors import UndefinedTable, InFailedSqlTransaction, NotNullViolation, OperationalError
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from typing import Optional, Union, Awaitable, Callable, Any
from urllib.parse import urlparse, quote
from version import __version__

from core.autoexec import Autoexec
from core.data.dataobject import DataObjectFactory
from core.data.node import Node, UploadStatus, SortOrder, FatalException
from core.data.instance import Instance
from core.data.impl.instanceimpl import InstanceImpl
from core.data.server import Server
from core.data.impl.serverimpl import ServerImpl
from core.services.registry import ServiceRegistry
from core.utils.helper import SettingsDict, YAMLError

# ruamel YAML support
from pykwalify.errors import SchemaError
from pykwalify.core import Core
from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError
yaml = YAML()


__all__ = [
    "NodeImpl"
]

LOGLEVEL = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL
}

REPO_URL = "https://api.github.com/repos/Special-K-s-Flightsim-Bots/DCSServerBot/releases"
LOGIN_URL = 'https://www.digitalcombatsimulator.com/gameapi/login/'
UPDATER_URL = 'https://www.digitalcombatsimulator.com/gameapi/updater/branch/{}/'
LICENSES_URL = 'https://www.digitalcombatsimulator.com/checklicenses.php'

# Internationalisation
_ = get_translation('core')


class NodeImpl(Node):

    def __init__(self, name: str, config_dir: Optional[str] = 'config'):
        super().__init__(name, config_dir)
        self.node = self  # to be able to address self.node
        self._public_ip: Optional[str] = None
        self.bot_version = __version__[:__version__.rfind('.')]
        self.sub_version = int(__version__[__version__.rfind('.') + 1:])
        self.dcs_branch = None
        self.dcs_version = None
        self.all_nodes: Optional[dict[str, dict]] = None
        self.instances: list[Instance] = list()
        self.update_pending = False
        self.before_update: dict[str, Callable[[], Awaitable[Any]]] = dict()
        self.after_update: dict[str, Callable[[], Awaitable[Any]]] = dict()
        self.locals = self.read_locals()
        self.log = self.init_logger()
        if sys.platform == 'win32':
            from os import system
            system(f"title DCSServerBot v{self.bot_version}.{self.sub_version}")
        self.log.info(f'DCSServerBot v{self.bot_version}.{self.sub_version} starting up ...')
        self.log.info(f'- Python version {platform.python_version()} detected.')
        self.install_plugins()
        self.plugins: list[str] = [x.lower() for x in self.config.get('plugins', [
            "mission", "scheduler", "help", "admin", "userstats", "missionstats", "creditsystem", "gamemaster", "cloud"
        ])]
        for plugin in [x.lower() for x in self.config.get('opt_plugins', [])]:
            if plugin not in self.plugins:
                self.plugins.append(plugin)
        # make sure, cloud is loaded last
        if 'cloud' in self.plugins:
            self.plugins.remove('cloud')
            self.plugins.append('cloud')
        self.db_version = None
        self.pool: Optional[ConnectionPool] = None
        self.apool: Optional[AsyncConnectionPool] = None
        self._master = None
        self.listen_address = self.locals.get('listen_address', '0.0.0.0')
        self.listen_port = self.locals.get('listen_port', 10042)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close_db()

    async def post_init(self):
        self.pool, self.apool = await self.init_db()
        try:
            async with self.apool.connection() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        INSERT INTO nodes (guild_id, node) VALUES (%s, %s) 
                        ON CONFLICT (guild_id, node) DO UPDATE SET last_seen = (NOW() AT TIME ZONE 'UTC')
                    """, (self.guild_id, self.name))
            self._master = await self.heartbeat()
        except (UndefinedTable, NotNullViolation, InFailedSqlTransaction):
            # some master tables have changed, so do the update first
            self._master = True
        if self._master:
            await self.update_db()
        self.init_instances()

    @property
    def master(self) -> bool:
        return self._master

    @master.setter
    def master(self, value: bool):
        if self._master != value:
            self._master = value

    @property
    def public_ip(self) -> str:
        return self._public_ip

    @property
    def installation(self) -> str:
        return os.path.expandvars(self.locals['DCS']['installation'])

    @property
    def extensions(self) -> dict:
        return self.locals.get('extensions', {})

    async def audit(self, message, *, user: Optional[Union[discord.Member, str]] = None,
                    server: Optional[Server] = None):
        from services import BotService, ServiceBus

        if self.master:
            await ServiceRegistry.get(BotService).bot.audit(message, user=user, server=server)
        else:
            ServiceRegistry.get(ServiceBus).send_to_node({
                "command": "rpc",
                "service": BotService.__name__,
                "method": "audit",
                "params": {
                    "message": message,
                    "user": f"<@{user.id}>" if isinstance(user, discord.Member) else user,
                    "server": server.name if server else ""
                }
            })

    def register_callback(self, what: str, name: str, func: Callable[[], Awaitable[Any]]):
        if what == 'before_dcs_update':
            self.before_update[name] = func
        else:
            self.after_update[name] = func

    def unregister_callback(self, what: str, name: str):
        if what == 'before_dcs_update':
            del self.before_update[name]
        else:
            del self.after_update[name]

    async def shutdown(self):
        await ServiceRegistry.shutdown()
        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        asyncio.get_event_loop().stop()

    async def restart(self):
        self.log.info("Restarting ...")
        await ServiceRegistry.shutdown()
        await self.aclose_db()
        os.execv(sys.executable, [os.path.basename(sys.executable), 'run.py'] + sys.argv[1:])

    def read_locals(self) -> dict:
        _locals = dict()
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        if os.path.exists(config_file):
            try:
                schema_files = ['./schemas/nodes_schema.yaml']
                schema_files.extend([str(x) for x in Path('./extensions/schemas').glob('*.yaml')])
                c = Core(source_file=config_file, schema_files=schema_files, file_encoding='utf-8')
                # TODO: change this to true after testing phase
                c.validate(raise_exception=False)
                self.all_nodes: dict = yaml.load(Path(config_file).read_text(encoding='utf-8'))
            except (MarkedYAMLError, SchemaError) as ex:
                raise YAMLError('config_file', ex)
            node: dict = self.all_nodes.get(self.name)
            if not node:
                raise FatalException(f'No configuration found for node {self.name} in {config_file}!')
            dirty = False
            # check if we need to secure the database URL
            database_url = node.get('database', {}).get('url')
            if database_url:
                url = urlparse(database_url)
                if url.password and url.password != 'SECRET':
                    utils.set_password('database', url.password)
                    port = url.port or 5432
                    node['database']['url'] = \
                        f"{url.scheme}://{url.username}:SECRET@{url.hostname}:{port}{url.path}?sslmode=prefer"
                    dirty = True
                    # we do not have a logger yet, so print it
                    print("Database password found, removing it from config.")
            password = node['DCS'].pop('dcs_password', node['DCS'].pop('password', None))
            if password:
                node['DCS']['user'] = node['DCS'].pop('dcs_user')
                utils.set_password('DCS', password)
                dirty = True
            if dirty:
                with open(config_file, 'w', encoding='utf-8') as f:
                    yaml.dump(self.all_nodes, f)
            return node
        raise FatalException(f"No {config_file} found. Exiting.")

    def init_logger(self):
        log = logging.getLogger(name='dcsserverbot')
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter(fmt=u'%(asctime)s.%(msecs)03d %(levelname)s\t%(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        formatter.converter = time.gmtime
        os.makedirs('logs', exist_ok=True)
        fh = CloudRotatingFileHandler(os.path.join('logs', f'dcssb-{self.name}.log'), encoding='utf-8',
                                      maxBytes=self.config['logging']['logrotate_size'],
                                      backupCount=self.config['logging']['logrotate_count'])
        fh.setLevel(LOGLEVEL[self.config['logging']['loglevel']])
        fh.setFormatter(formatter)
        fh.doRollover()
        log.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        log.addHandler(ch)
        # Database logging
        log2 = logging.getLogger(name='psycopg.pool')
        log2.setLevel(logging.ERROR)
        log2.addHandler(ch)
        # Pykwalify logging
        log3 = logging.getLogger('pykwalify.core')
        log3.addHandler(ch)
        log3.addHandler(fh)
        return log

    async def init_db(self) -> tuple[ConnectionPool, AsyncConnectionPool]:
        url = self.config.get("database", self.locals.get('database'))['url']
        try:
            url = url.replace('SECRET', quote(utils.get_password('database')) or '')
        except ValueError:
            pass
        # quick connection check
        db_available = False
        max_attempts = self.config.get("database", self.locals.get('database')).get('max_retries', 10)
        while not db_available:
            try:
                with psycopg.connect(url):
                    self.log.info("- Connection to database established.")
                    db_available = True
            except OperationalError:
                max_attempts -= 1
                if not max_attempts:
                    raise
                self.log.warning("- Database not available, trying again in 5s ...")
                await asyncio.sleep(5)
        pool_min = self.config.get("database", self.locals.get('database')).get('pool_min', 4)
        pool_max = self.config.get("database", self.locals.get('database')).get('pool_max', 10)
        max_idle = self.config.get("database", self.locals.get('database')).get('max_idle', 10 * 60.0)
        timeout = 60.0 if self.locals.get('slow_system', False) else 30.0
        db_pool = ConnectionPool(url, min_size=2, max_size=4,
                                 check=ConnectionPool.check_connection, max_idle=max_idle, timeout=timeout)
        db_apool = AsyncConnectionPool(conninfo=url, min_size=pool_min, max_size=pool_max,
                                       check=AsyncConnectionPool.check_connection, max_idle=max_idle, timeout=timeout)
        return db_pool, db_apool

    def close_db(self):
        if self.pool:
            try:
                self.pool.close()
            except Exception as ex:
                self.log.exception(ex)
        if self.apool:
            try:
                asyncio.run(self.apool.close())
            except Exception as ex:
                self.log.exception(ex)

    async def aclose_db(self):
        if self.pool:
            try:
                self.pool.close()
            except Exception as ex:
                self.log.exception(ex)
        if self.apool:
            try:
                await self.apool.close()
            except Exception as ex:
                self.log.exception(ex)

    def init_instances(self):
        grouped = defaultdict(list)
        for server_name, instance_name in utils.findDCSInstances():
            grouped[server_name].append(instance_name)
        duplicates = {server_name: instances for server_name, instances in grouped.items() if len(instances) > 1}
        for server_name, instances in duplicates.items():
            self.log.warning("Duplicate server \"{}\" defined in instance {}!".format(server_name, ', '.join(instances)))
        for _name, _element in self.locals.pop('instances', {}).items():
            instance = DataObjectFactory().new(InstanceImpl, node=self, name=_name, locals=_element)
            self.instances.append(instance)

    async def update_db(self):
        # Initialize the database
        async with self.apool.connection() as conn:
            async with conn.transaction():
                # check if there is an old database already
                cursor = await conn.execute("""
                    SELECT tablename FROM pg_catalog.pg_tables WHERE tablename IN ('version', 'plugins')
                """)
                tables = [x[0] async for x in cursor]
                # initial setup
                if len(tables) == 0:
                    self.log.info('Creating Database ...')
                    with open('sql/tables.sql', mode='r') as tables_sql:
                        for query in tables_sql.readlines():
                            self.log.debug(query.rstrip())
                            await cursor.execute(query.rstrip())
                    self.log.info('Database created.')
                else:
                    # version table missing (DB version <= 1.4)
                    if 'version' not in tables:
                        await conn.execute("CREATE TABLE IF NOT EXISTS version (version TEXT PRIMARY KEY)")
                        await conn.execute("INSERT INTO version (version) VALUES ('v1.4')")
                    cursor = await conn.execute('SELECT version FROM version')
                    self.db_version = (await cursor.fetchone())[0]
                    while os.path.exists(f'sql/update_{self.db_version}.sql'):
                        old_version = self.db_version
                        with open(f'sql/update_{self.db_version}.sql', mode='r') as tables_sql:
                            for query in tables_sql.readlines():
                                self.log.debug(query.rstrip())
                                await conn.execute(query.rstrip())
                        cursor = await conn.execute('SELECT version FROM version')
                        self.db_version = (await cursor.fetchone())[0]
                        self.log.info(f'Database upgraded from {old_version} to {self.db_version}.')

    def install_plugins(self):
        for file in Path('plugins').glob('*.zip'):
            path = file.__str__()
            self.log.info('- Unpacking plugin "{}" ...'.format(os.path.basename(path).replace('.zip', '')))
            shutil.unpack_archive(path, '{}'.format(path.replace('.zip', '')))
            os.remove(path)

    async def _upgrade_pending_git(self) -> bool:
        import git

        try:
            with closing(git.Repo('.')) as repo:
                current_hash = repo.head.commit.hexsha
                origin = repo.remotes.origin
                origin.fetch()
                new_hash = origin.refs[repo.active_branch.name].object.hexsha
                if new_hash != current_hash:
                    return True
        except git.InvalidGitRepositoryError:
            return await self._upgrade_pending_non_git()
        except git.GitCommandError as ex:
            self.log.error('  => Autoupdate failed!')
            changed_files = repo.index.diff(None)
            if changed_files:
                self.log.error('     Please revert back the changes in these files:')
                for item in changed_files:
                    self.log.error(f'     ./{item.a_path}')
            else:
                self.log.error(ex)
            return False
        except ValueError as ex:
            self.log.error(ex)
            return False

    async def _upgrade_pending_non_git(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REPO_URL) as response:
                    result = await response.json()
                    current_version = __version__
                    latest_version = result[0]["tag_name"]

                    if re.sub('^v', '', latest_version) > re.sub('^v', '', current_version):
                        return True
        except aiohttp.ClientResponseError as ex:
            # ignore rate limits
            if ex.status == 403:
                pass
            raise
        return False

    async def upgrade_pending(self) -> bool:
        self.log.debug('- Checking for updates...')
        try:
            rc = await self._upgrade_pending_git()
        except ImportError:
            rc = await self._upgrade_pending_non_git()
        except Exception as ex:
            self.log.exception(ex)
            raise
        if not rc:
            self.log.debug('- No update found for DCSServerBot.')
        return rc

    async def upgrade(self):
        # We do not want to run an upgrade, if we are on a cloud drive, so just restart in this case
        if not self.master and self.locals.get('cloud_drive', True):
            await self.restart()
            return
        elif await self.upgrade_pending():
            if self.master:
                async with self.apool.connection() as conn:
                    async with conn.transaction():
                        await conn.execute("UPDATE cluster SET update_pending = TRUE WHERE guild_id = %s",
                                           (self.guild_id, ))
            await ServiceRegistry.shutdown()
            await self.aclose_db()
            os.execv(sys.executable, [os.path.basename(sys.executable), 'update.py'] + sys.argv[1:])

    async def get_dcs_branch_and_version(self) -> tuple[str, str]:
        if not self.dcs_branch or not self.dcs_version:
            with open(os.path.join(self.installation, 'autoupdate.cfg'), mode='r', encoding='utf8') as cfg:
                data = json.load(cfg)
            self.dcs_branch = data.get('branch', 'release')
            self.dcs_version = data['version']
            if "openbeta" in self.dcs_branch:
                self.log.debug("You're running DCS OpenBeta, which is discontinued. "
                               "Use /dcs update, if you want to switch to the release branch.")
        return self.dcs_branch, self.dcs_version

    async def update(self, warn_times: list[int], branch: Optional[str] = None) -> int:
        from services import ServiceBus

        async def shutdown_with_warning(server: Server):
            if server.is_populated():
                shutdown_in = max(warn_times) if len(warn_times) else 0
                while shutdown_in > 0:
                    for warn_time in warn_times:
                        if warn_time == shutdown_in:
                            server.sendPopupMessage(
                                Coalition.ALL,
                                _('Server is going down for a DCS update in {}!').format(utils.format_time(warn_time)))
                    await asyncio.sleep(1)
                    shutdown_in -= 1
            await server.shutdown()

        async def do_update(branch: Optional[str] = None) -> int:
            # disable any popup on the remote machine
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= (subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW)
                startupinfo.wShowWindow = subprocess.SW_HIDE
                startupinfo.wShowWindow = subprocess.SW_HIDE
            else:
                startupinfo = None

            def run_subprocess() -> int:
                try:
                    cmd = [os.path.join(self.installation, 'bin', 'dcs_updater.exe'), '--quiet', 'update']
                    if branch:
                        cmd.append(f"@{branch}")

                    process = subprocess.run(
                        cmd, startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    if branch and process.returncode == 0:
                        # check if the branch has been changed
                        config = os.path.join(self.installation, 'autoupdate.cfg')
                        with open(config, mode='r') as infile:
                            data = json.load(infile)
                        if data['branch'] != branch:
                            data['branch'] = branch
                            with open(config, mode='w') as outfile:
                                json.dump(data, outfile, indent=2)
                    return process.returncode
                except Exception as ex:
                    self.log.exception(ex)
                    return -1

            return await asyncio.to_thread(run_subprocess)

        self.update_pending = True
        to_start = []
        in_maintenance = []
        tasks = []
        bus = ServiceRegistry.get(ServiceBus)
        for server in [x for x in bus.servers.values() if not x.is_remote]:
            if server.maintenance:
                in_maintenance.append(server)
            else:
                server.maintenance = True
            if server.status not in [Status.UNREGISTERED, Status.SHUTDOWN]:
                to_start.append(server)
                tasks.append(asyncio.create_task(shutdown_with_warning(server)))
        # wait for DCS servers to shut down
        if tasks:
            await asyncio.gather(*tasks)
        self.log.info(f"Updating {self.installation} ...")
        # call before update hooks
        for callback in self.before_update.values():
            await callback()
        rc = await do_update(branch)
        if rc == 0:
            self.dcs_branch = self.dcs_version = None
            if self.locals['DCS'].get('desanitize', True):
                if not self.locals['DCS'].get('cloud', False) or self.master:
                    utils.desanitize(self)
            # call after update hooks
            for callback in self.after_update.values():
                await callback()
            self.log.info(f"{self.installation} updated to the latest version.")
        for server in [x for x in bus.servers.values() if not x.is_remote]:
            if server not in in_maintenance:
                # let the scheduler do its job
                server.maintenance = False
            if server in to_start:
                try:
                    # the server was running before (being in maintenance mode), so start it again
                    await server.startup()
                except (TimeoutError, asyncio.TimeoutError):
                    self.log.warning(f'Timeout while starting {server.display_name}, please check it manually!')
        if rc == 0:
            self.update_pending = False
        return rc

    async def handle_module(self, what: str, module: str):
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= (subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW)
            startupinfo.wShowWindow = subprocess.SW_HIDE
        else:
            startupinfo = None

        def run_subprocess():
            subprocess.run(
                [os.path.join(self.installation, 'bin', 'dcs_updater.exe'), '--quiet', what, module],
                startupinfo=startupinfo
            )

        await asyncio.to_thread(run_subprocess)

    async def get_installed_modules(self) -> list[str]:
        with open(os.path.join(self.installation, 'autoupdate.cfg'), mode='r', encoding='utf8') as cfg:
            data = json.load(cfg)
        return data['modules']

    async def get_available_modules(self) -> list[str]:
        licenses = {
            "CAUCASUS_terrain",
            "NEVADA_terrain",
            "NORMANDY_terrain",
            "PERSIANGULF_terrain",
            "THECHANNEL_terrain",
            "SYRIA_terrain",
            "MARIANAISLANDS_terrain",
            "FALKLANDS_terrain",
            "SINAIMAP_terrain",
            "KOLA_terrain",
            "WWII-ARMOUR",
            "SUPERCARRIER"
        }
        user = self.locals['DCS'].get('user')
        if not user:
            return list(licenses)
        password = utils.get_password('DCS')
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
                ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
            response = await session.post(LOGIN_URL, data={"login": user, "password": password})
            if response.status == 200:
                async with session.get(LICENSES_URL) as response:
                    if response.status == 200:
                        all_licenses = (await response.text(encoding='utf8')).split('<br>')[1:]
                        for lic in all_licenses:
                            if lic.endswith('_terrain'):
                                licenses.add(lic)
            return list(licenses)

    async def get_latest_version(self, branch: str) -> Optional[str]:
        user = self.locals['DCS'].get('user')
        if user:
            password = utils.get_password('DCS')
            auth = aiohttp.BasicAuth(login=user, password=password)
        else:
            auth = None
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
                ssl=ssl.create_default_context(cafile=certifi.where())), auth=auth) as session:
            async with session.get(UPDATER_URL.format(branch)) as response:
                if response.status == 200:
                    return json.loads(gzip.decompress(await response.read()))['versions2'][-1]['version']
        return None

    async def register(self):
        self._public_ip = self.locals.get('public_ip')
        if not self._public_ip:
            self._public_ip = await utils.get_public_ip()
            self.log.info(f"- Public IP registered as: {self.public_ip}")
        if self.locals['DCS'].get('autoupdate', False):
            if not self.locals['DCS'].get('cloud', False) or self.master:
                self.autoupdate.start()
        else:
            branch, old_version = await self.get_dcs_branch_and_version()
            try:
                new_version = await self.get_latest_version(branch)
                if new_version and old_version != new_version:
                    self.log.warning(
                        f"- Your DCS World version is outdated. Consider upgrading to version {new_version}.")
            except Exception:
                self.log.warning("Version check failed, possible auth-server outage.")

    async def unregister(self):
        async with self.apool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM nodes WHERE guild_id = %s AND node = %s", (self.guild_id, self.name))
        if self.locals['DCS'].get('autoupdate', False):
            if not self.locals['DCS'].get('cloud', False) or self.master:
                self.autoupdate.cancel()

    async def heartbeat(self) -> bool:
        try:
            async with self.apool.connection() as conn:
                async with conn.transaction():
                    async with conn.cursor(row_factory=dict_row) as cursor:
                        try:
                            await cursor.execute("""
                                SELECT NOW() AT TIME ZONE 'UTC' AS now, * FROM nodes 
                                WHERE guild_id = %s FOR UPDATE
                            """, (self.guild_id, ))
                            all_nodes = await cursor.fetchall()
                            await cursor.execute("""
                                SELECT c.master, c.version, c.update_pending 
                                FROM cluster c, nodes n 
                                WHERE c.guild_id = %s AND c.guild_id = n.guild_id AND c.master = n.node
                            """, (self.guild_id, ))
                            cluster = await cursor.fetchone()
                            # No master there? we take it!
                            if not cluster:
                                await cursor.execute("""
                                    INSERT INTO cluster (guild_id, master, version) VALUES (%s, %s, %s)
                                    ON CONFLICT (guild_id) DO UPDATE 
                                    SET master = excluded.master, version = excluded.version
                                """, (self.guild_id, self.name, __version__))
                                return True
                            # I am the master
                            if cluster['master'] == self.name:
                                # set the master here already to avoid race conditions
                                self.master = True
                                if cluster['update_pending']:
                                    if not await self.upgrade_pending():
                                        # we have just finished updating, so restart all other nodes (if there are any)
                                        for node in await self.get_active_nodes():
                                            # TODO: we might not have bus access here yet, so be our own bus (dirty)
                                            data = {
                                                "command": "rpc",
                                                "object": "Node",
                                                "method": "upgrade"
                                            }
                                            await conn.execute("""
                                                INSERT INTO intercom (guild_id, node, data) VALUES (%s, %s, %s)
                                            """, (self.guild_id, node, Json(data)))
                                        # clear the update flag
                                        await cursor.execute("""
                                            UPDATE cluster SET update_pending = FALSE, version = %s WHERE guild_id = %s
                                        """, (__version__, self.guild_id))
                                    else:
                                        # something went wrong, we need to upgrade again
                                        await self.upgrade()
                                elif version.parse(cluster['version']) != version.parse(__version__):
                                    if version.parse(cluster['version']) > version.parse(__version__):
                                        self.log.warning(
                                            f"Bot version downgraded from {cluster['version']} to {__version__}. "
                                            f"This could lead to unexpected behavior if there have been database schema "
                                            f"changes.")
                                    await cursor.execute("UPDATE cluster SET version = %s WHERE guild_id = %s",
                                                         (__version__, self.guild_id))
                                return True
                            # we are not the master, the update is pending, we will not take over
                            if cluster['update_pending']:
                                return False
                            # we have a version mismatch on the agent, a cloud sync might still be pending
                            if version.parse(__version__) < version.parse(cluster['version']):
                                self.log.error(f"We are running version {__version__} where the master is on version "
                                               f"{cluster['version']} already. Trying to upgrade ...")
                                # TODO: we might not have bus access here yet, so be our own bus (dirty)
                                data = {
                                    "command": "rpc",
                                    "object": "Node",
                                    "method": "upgrade"
                                }
                                await cursor.execute("""
                                    INSERT INTO intercom (guild_id, node, data) VALUES (%s, %s, %s)
                                """, (self.guild_id, self.name, Json(data)))
                                return False
                            elif version.parse(__version__) > version.parse(cluster['version']):
                                self.log.warning(f"This node is running on version {__version__} where the master still "
                                                 f"runs on {cluster['version']}. You need to upgrade your master node!")
                            # we are not the master, but we are the preferred one, taking over
                            if self.locals.get('preferred_master', False):
                                await cursor.execute("UPDATE cluster SET master = %s WHERE guild_id = %s",
                                                     (self.name, self.guild_id))
                                return True
                            # else, check if the running master is probably dead...
                            for row in all_nodes:
                                if row['node'] == self.name:
                                    continue
                                if row['node'] == cluster['master']:
                                    if (row['now'] - row['last_seen']).total_seconds() > self.locals.get('heartbeat', 30):
                                        # the master is dead, long live the master
                                        await cursor.execute("UPDATE cluster SET master = %s WHERE guild_id = %s",
                                                             (self.name, self.guild_id))
                                        return True
                                    return False
                            # we can not find a master - take over
                            await cursor.execute("UPDATE cluster SET master = %s WHERE guild_id = %s",
                                                 (self.name, self.guild_id))
                            return True
                        except UndefinedTable:
                            return True
                        except Exception as e:
                            self.log.exception(e)
                            return self.master
                        finally:
                            await cursor.execute("""
                                UPDATE nodes SET last_seen = NOW() AT TIME ZONE 'UTC' WHERE guild_id = %s AND node = %s
                            """, (self.guild_id, self.name))
        except OperationalError as ex:
            self.log.error(ex)
            return self.master

    async def get_active_nodes(self) -> list[str]:
        async with self.apool.connection() as conn:
            cursor = await conn.execute("""
                SELECT node FROM nodes 
                WHERE guild_id = %s
                AND node <> %s
                AND last_seen > (NOW() AT TIME ZONE 'UTC' - interval '1 minute')
            """, (self.guild_id, self.name))
            return [row[0] async for row in cursor]

    async def shell_command(self, cmd: str, timeout: int = 60) -> Optional[tuple[str, str]]:
        def run_subprocess():
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return proc.communicate(timeout=timeout)

        self.log.debug('Running shell-command: ' + cmd)
        try:
            stdout, stderr = await asyncio.to_thread(run_subprocess)
            return (stdout.decode('cp1252', 'ignore') if stdout else None,
                    stderr.decode('cp1252', 'ignore') if stderr else None)
        except subprocess.TimeoutExpired:
            raise TimeoutError()

    async def read_file(self, path: str) -> Union[bytes, int]:
        path = os.path.expandvars(path)
        if self.node.master:
            async with aiofiles.open(path, mode='rb') as file:
                return await file.read()
        else:
            async with self.apool.connection() as conn:
                async with conn.transaction():
                    async with aiofiles.open(path, mode='rb') as file:
                        await conn.execute("INSERT INTO files (guild_id, name, data) VALUES (%s, %s, %s)",
                                           (self.guild_id, path, psycopg.Binary(await file.read())))
                    cursor = await conn.execute("SELECT currval('files_id_seq')")
                    return (await cursor.fetchone())[0]

    async def write_file(self, filename: str, url: str, overwrite: bool = False) -> UploadStatus:
        if os.path.exists(filename) and not overwrite:
            return UploadStatus.FILE_EXISTS

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    try:
                        # make sure the directory exists
                        os.makedirs(os.path.dirname(filename), exist_ok=True)
                        async with aiofiles.open(filename, mode='wb') as outfile:
                            await outfile.write(await response.read())
                    except Exception as ex:
                        self.log.error(ex)
                        return UploadStatus.WRITE_ERROR
                else:
                    return UploadStatus.READ_ERROR
        return UploadStatus.OK

    async def list_directory(self, path: str, pattern: str, order: Optional[SortOrder] = SortOrder.DATE) -> list[str]:
        directory = Path(os.path.expandvars(path))
        ret = []
        for file in sorted(directory.glob(pattern), key=os.path.getmtime if order == SortOrder.DATE else None,
                           reverse=True):
            ret.append(os.path.join(directory.__str__(), file.name))
        return ret

    async def remove_file(self, path: str):
        os.remove(path)

    async def rename_file(self, old_name: str, new_name: str, *, force: Optional[bool] = False):
        shutil.move(old_name, new_name, copy_function=shutil.copy2 if force else None)

    async def rename_server(self, server: Server, new_name: str):
        from services import BotService, ServiceBus

        if not self.master:
            self.log.error(
                f"Rename request received for server {server.name} that should have gone to the master node!")
            return
        # we are doing the plugin changes, as we are the master
        await ServiceRegistry.get(BotService).rename_server(server, new_name)
        # update the ServiceBus
        ServiceRegistry.get(ServiceBus).rename_server(server, new_name)
        # change the proxy name for remote servers (local ones will be renamed by ServerImpl)
        if server.is_remote:
            server.name = new_name

    @tasks.loop(minutes=5.0)
    async def autoupdate(self):
        from services import BotService, ServiceBus

        # don't run, if an update is currently running
        if self.update_pending:
            return
        try:
            try:
                branch, old_version = await self.get_dcs_branch_and_version()
                new_version = await self.get_latest_version(branch)
            except Exception:
                self.log.warning("Update check failed, possible server outage at ED.")
                return
            if new_version and old_version != new_version:
                self.log.info('A new version of DCS World is available. Auto-updating ...')
                rc = await self.update([300, 120, 60])
                if rc == 0:
                    ServiceRegistry.get(ServiceBus).send_to_node({
                        "command": "rpc",
                        "service": BotService.__name__,
                        "method": "audit",
                        "params": {
                            "message": f"DCS World updated to version {new_version} on node {self.node.name}."
                        }
                    })
                else:
                    ServiceRegistry.get(ServiceBus).send_to_node({
                        "command": "rpc",
                        "service": BotService.__name__,
                        "method": "alert",
                        "params": {
                            "title": "DCS Update Issue",
                            "message": f"DCS World could not be updated on node {self.name} due to an error ({rc})!"
                        }
                    })
        except aiohttp.ClientError as ex:
            self.log.warning(ex)
        except Exception as ex:
            self.log.exception(ex)

    @autoupdate.before_loop
    async def before_autoupdate(self):
        from services import ServiceBus

        # wait for all servers to be in a proper state
        while True:
            await asyncio.sleep(1)
            bus = ServiceRegistry.get(ServiceBus)
            if not bus:
                continue
            server_initialized = True
            for server in bus.servers.values():
                if server.status == Status.UNREGISTERED:
                    server_initialized = False
            if server_initialized:
                break

    async def add_instance(self, name: str, *, template: Optional[Instance] = None) -> Instance:
        max_bot_port = 6666-1
        max_dcs_port = 10308-10
        max_webgui_port = 8088-2
        for instance in self.instances:
            if instance.bot_port > max_bot_port:
                max_bot_port = instance.bot_port
            if instance.dcs_port > max_dcs_port:
                max_dcs_port = instance.dcs_port
            if instance.webgui_port > max_webgui_port:
                max_webgui_port = instance.webgui_port
        os.makedirs(os.path.join(SAVED_GAMES, name), exist_ok=True)
        instance = DataObjectFactory().new(InstanceImpl, node=self, name=name, locals={
            "bot_port": max_bot_port + 1,
            "dcs_port": max_dcs_port + 10,
            "webgui_port": max_webgui_port + 2
        })
        os.makedirs(os.path.join(instance.home, 'Config'), exist_ok=True)
        # should we copy from a template
        if template:
            shutil.copy2(os.path.join(template.home, 'Config', 'autoexec.cfg'),
                         os.path.join(instance.home, 'Config'))
            shutil.copy2(os.path.join(template.home, 'Config', 'serverSettings.lua'),
                         os.path.join(instance.home, 'Config'))
            shutil.copy2(os.path.join(template.home, 'Config', 'options.lua'),
                         os.path.join(instance.home, 'Config'))
            shutil.copy2(os.path.join(template.home, 'Config', 'network.vault'),
                         os.path.join(instance.home, 'Config'))
            if template.extensions and template.extensions.get('SRS'):
                shutil.copy2(os.path.expandvars(template.extensions['SRS']['config']),
                             os.path.join(instance.home, 'Config', 'SRS.cfg'))
        autoexec = Autoexec(instance=instance)
        autoexec.webgui_port = instance.webgui_port
        autoexec.crash_report_mode = "silent"
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        with open(config_file, mode='r', encoding='utf-8') as infile:
            config = yaml.load(infile)
        config[self.name]['instances'][instance.name] = {
            "home": instance.home,
            "bot_port": instance.bot_port
        }
        with open(config_file, mode='w', encoding='utf-8') as outfile:
            yaml.dump(config, outfile)
        settings_path = os.path.join(instance.home, 'Config', 'serverSettings.lua')
        if os.path.exists(settings_path):
            settings = SettingsDict(self, settings_path, root='cfg')
            settings['port'] = instance.dcs_port
            settings['name'] = 'n/a'
        server = DataObjectFactory().new(ServerImpl, node=self.node, port=instance.bot_port, name='n/a')
        instance.server = server
        self.instances.append(instance)
        return instance

    async def delete_instance(self, instance: Instance, remove_files: bool) -> None:
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        with open(config_file, mode='r', encoding='utf-8') as infile:
            config = yaml.load(infile)
        del config[self.name]['instances'][instance.name]
        with open(config_file, mode='w', encoding='utf-8') as outfile:
            yaml.dump(config, outfile)
        self.instances.remove(instance)
        async with self.apool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM instances WHERE instance = %s", (instance.name, ))
        if remove_files:
            shutil.rmtree(instance.home, ignore_errors=True)

    async def rename_instance(self, instance: Instance, new_name: str) -> None:
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        with open(config_file, mode='r', encoding='utf-8') as infile:
            config = yaml.load(infile)
        new_home = os.path.join(os.path.dirname(instance.home), new_name)
        os.rename(instance.home, new_home)
        config[self.name]['instances'][new_name] = config[self.name]['instances'][instance.name].copy()
        config[self.name]['instances'][new_name]['home'] = new_home
        async with self.apool.connection() as conn:
            async with conn.transaction():
                await conn.execute("""
                    UPDATE instances SET instance = %s 
                    WHERE node = %s AND instance = %s
                """, (new_name, instance.node.name, instance.name, ))
        instance.name = new_name
        instance.locals['home'] = new_home
        del config[self.name]['instances'][instance.name]
        with open(config_file, mode='w', encoding='utf-8') as outfile:
            yaml.dump(config, outfile)

    async def find_all_instances(self) -> list[tuple[str, str]]:
        return utils.findDCSInstances()

    async def migrate_server(self, server: Server, instance: Instance) -> None:
        from services import ServiceBus

        await server.node.unregister_server(server)
        server = DataObjectFactory().new(ServerImpl, node=self.node, port=instance.bot_port, name=server.name)
        server.status = Status.SHUTDOWN
        ServiceRegistry.get(ServiceBus).servers[server.name] = server
        instance.server = server
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        with open(config_file, mode='r', encoding='utf-8') as infile:
            config = yaml.load(infile)
        config[self.name]['instances'][instance.name]['server'] = server.name
        with open(config_file, mode='w', encoding='utf-8') as outfile:
            yaml.dump(config, outfile)

    async def unregister_server(self, server: Server) -> None:
        config_file = os.path.join(self.config_dir, 'nodes.yaml')
        instance = server.instance
        instance.server = None
        with open(config_file, mode='r', encoding='utf-8') as infile:
            config = yaml.load(infile)
        del config[self.name]['instances'][instance.name]['server']
        with open(config_file, mode='w', encoding='utf-8') as outfile:
            yaml.dump(config, outfile)
