import platform
import psutil
import psycopg2
from contextlib import closing
from core import utils, Plugin, DCSServerBot, TEventListener, Status, PaginationReport, PluginRequiredError
from discord.ext import tasks, commands
from typing import Type, Optional
from .listener import ServerStatsListener


class AgentServerStats(Plugin):

    def __init__(self, bot: DCSServerBot, eventlistener: Type[TEventListener] = None):
        super().__init__(bot, eventlistener)
        self.cleanup.start()
        self.schedule.start()
        self.io_counters = {}
        self.net_io_counters = None

    def cog_unload(self):
        self.cleanup.cancel()
        self.schedule.cancel()
        super().cog_unload()

    @commands.command(description='Shows servers load', usage='[period]')
    @utils.has_role('Admin')
    @commands.guild_only()
    async def serverload(self, ctx, period: Optional[str], server_name: Optional[str]):
        report = PaginationReport(self.bot, ctx, self.plugin, 'serverload.json')
        await report.render(period=period, server_name=server_name, agent_host=platform.node())

    @tasks.loop(minutes=1.0)
    async def schedule(self):
        conn = self.pool.getconn()
        try:
            with closing(conn.cursor()) as cursor:
                for server_name, server in self.globals.items():
                    if server['status'] not in [Status.RUNNING, Status.PAUSED]:
                        continue
                    if server['server_name'] in self.bot.player_data:
                        players = self.bot.player_data[server['server_name']]
                        users = len(players[players['active'] == True]) + 1
                    else:
                        users = 0
                    mission_id = self.globals[server_name]['mission_id'] if 'mission_id' in server else -1
                    process = utils.find_process('DCS.exe', server['installation'])
                    cpu = process.cpu_percent()
                    memory = process.memory_full_info()
                    io_counters = process.io_counters()
                    if process.pid not in self.io_counters:
                        write_bytes = read_bytes = 0
                    else:
                        write_bytes = int((io_counters.write_bytes - self.io_counters[process.pid].write_bytes) / 60)
                        read_bytes = int((io_counters.read_bytes - self.io_counters[process.pid].read_bytes) / 60)
                    self.io_counters[process.pid] = io_counters
                    net_io_counters = psutil.net_io_counters(pernic=False)
                    if not self.net_io_counters:
                        bytes_sent = bytes_recv = 0
                    else:
                        bytes_sent = int((net_io_counters.bytes_sent - self.net_io_counters.bytes_sent) / 60)
                        bytes_recv = int((net_io_counters.bytes_recv - self.net_io_counters.bytes_recv) / 60)
                    self.net_io_counters = net_io_counters
                    if server_name in self.eventlistener.fps:
                        cursor.execute('INSERT INTO serverstats (server_name, agent_host, mission_id, users, status, '
                                       'cpu, mem_total, mem_ram, read_bytes, write_bytes, bytes_sent, bytes_recv, '
                                       'fps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                                       (server_name, platform.node(), mission_id, users, server['status'].name, cpu,
                                        memory.private, memory.uss, read_bytes, write_bytes, bytes_sent, bytes_recv,
                                        self.eventlistener.fps[server_name]))
                        conn.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            conn.rollback()
            self.log.exception(error)
        finally:
            self.pool.putconn(conn)

    @tasks.loop(hours=12.0)
    async def cleanup(self):
        conn = self.pool.getconn()
        try:
            with closing(conn.cursor()) as cursor:
                cursor.execute("DELETE FROM serverstats WHERE time < (CURRENT_TIMESTAMP - interval '1 week')")
            conn.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            conn.rollback()
            self.log.exception(error)
        finally:
            self.pool.putconn(conn)


class MasterServerStats(AgentServerStats):

    @commands.command(description='Shows servers statistics', usage='[period]')
    @utils.has_role('Admin')
    @commands.guild_only()
    async def serverstats(self, ctx, period: Optional[str], server_name: Optional[str]):
        report = PaginationReport(self.bot, ctx, self.plugin, 'serverstats.json')
        await report.render(period=period, server_name=server_name)


def setup(bot: DCSServerBot):
    if 'userstats' not in bot.plugins:
        raise PluginRequiredError('userstats')
    if bot.config.getboolean('BOT', 'MASTER') is True:
        bot.add_cog(MasterServerStats(bot, ServerStatsListener))
    else:
        bot.add_cog(AgentServerStats(bot, ServerStatsListener))