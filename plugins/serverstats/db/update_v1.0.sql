UPDATE plugins SET version = 'v1.1' WHERE plugin = 'serverstats';
ALTER TABLE serverstats ADD COLUMN agent_host TEXT;
UPDATE serverstats s SET agent_host = (SELECT agent_host FROM servers WHERE server_name = s.server_name)
