��    E      D  a   l      �  6   �     (     :  	   L  R   V    �  8   �  $   �  $    �   A
  �   �
  [  �     �     �            #   )  (   M     v     �  1   �     �       9     &   U  #   |  2   �  @   �  1     .   F  *   u     �  *   �  :   �          1      I  ,   j     �  2   �  <   �  3     4   A  R   v  Y   �  M   #  <   q  3   �  &   �  �   	  :   �  ?   �  �   '  )   �  B      G   C  ?   �  8   �  /     S   4  0   �  6   �  [   �  "   L  f   o  6   �  "     
   0     ;  /   �     �          "  ^   0  (  �  ;   �  #   �  >    �   W  �   "  u  �     3      Q      n      �   -   �   4   �   3   �   ,   ,!  8   Y!  %   �!  !   �!  ;   �!  :   "  )   Q"  F   {"  :   �"  3   �"  ;   1#      m#     �#  '   �#  ;   �#     $     $$  )   =$  <   g$     �$  .   �$  8   �$  /   %  7   C%  f   {%  W   �%  W   :&  6   �&  6   �&  0    '  �   1'  C   �'  P   (  d   i(  B   �(  j   )  j   |)  >   �)  C   &*  5   j*  `   �*  Q   +  >   S+  f   �+  4   �+  p   .,  H   �,  -   �,     -         3   2   )          :                                  /      D                                B   (       C   >         4             +   7   E   "       @          
          5   *          9           .   ?   '   $      6       ;   	       A   1      <      0      %             &   #          !   =                        -          ,           8    

All set. Writing / updating your config files now... 
1. General Setup 
2. Discord Setup 
Aborted. 
DCS server "{}" found.
Would you like to manage this server through DCSServerBot? 
For a successful installation, you need to fulfill the following prerequisites:

    1. Installation of PostgreSQL from https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
    2. A Discord TOKEN for your bot from https://discord.com/developers/applications

 
Please provide a channel ID for audit events (optional) 
Searching for DCS installations ... 
The Status Channel should be readable by everyone and only writable by the bot.
The Chat Channel should be readable and writable by everyone.
The Admin channel - central or not - should only be readable and writable by Admin and DCS Admin users.

You can create these channels now, as I will ask for the IDs in a bit.
DCSServerBot needs the following permissions on them to work:

    - View Channel
    - Send Messages
    - Read Messages
    - Read Message History
    - Add Reactions
    - Attach Files
    - Embed Links
    - Manage Messages

 
The bot can either use a dedicated admin channel for each server or a central admin channel for all servers.
If you want to use a central one, please provide the ID (optional) 
We now need to setup your Discord roles and channels.
DCSServerBot creates a role mapping for your bot users. It has the following internal roles: 
[green]Your basic DCSServerBot configuration is finished.[/]

You can now review the created configuration files below your config folder of your DCSServerBot-installation.
There is much more to explore and to configure, so please don't forget to have a look at the documentation!

You can start DCSServerBot with:

    [bright_black]run.cmd[/]

 
{}. DCS Server Setup 
{}. Database Setup 
{}. Node Setup - Created {} Aborted: No DCS installation found. Aborted: No valid Database URL provided. Aborted: configuration exists Aborted: missing requirements. Adding instance {instance} with server {name} ... DCS-SRS installation path: {} DCS-SRS not configured. DCSServerBot uses up to {} channels per supported server: Directory not found. Please try again. Do you remember the password of {}? Do you want DCSServerBot to autostart this server? Do you want your DCS installation being auto-updated by the bot? Do you want your DCSServerBot being auto-updated? Enter the hostname of your PostgreSQL-database Enter the port to your PostgreSQL-database For admin commands. Have you fulfilled all these requirements? I've found multiple installations of DCS World on this PC: Installation finished. Instance {} configured. No configured DCS servers found. Normal user, can pull statistics, ATIS, etc. Other Please enter the ID of your [bold]Admin Channel[/] Please enter the ID of your [bold]Chat Channel[/] (optional) Please enter the ID of your [bold]Status Channel[/] Please enter the path to your DCS World installation Please enter the path to your DCS-SRS installation.
Press ENTER, if there is none. Please enter your Discord Guild ID (right click on your Discord server, "Copy Server ID") Please enter your Owner ID (right click on your discord user, "Copy User ID") Please enter your PostgreSQL master password (user=postgres) Please enter your discord TOKEN (see documentation) Please enter your password for user {} Please separate roles by comma, if you want to provide more than one.
You can keep the defaults, if unsure and create the respective roles in your Discord server. Please specify, which installation you want the bot to use SRS configuration could not be created, manual setup necessary. The bot can be set to the same language, which means, that all Discord and in-game messages will be in your language as well. Would you like me to configure the bot this way? To display the mission and player status. Users can delete data, change the bot, run commands on your server Users can upload missions, start/stop DCS servers, kick/ban users, etc. Which role(s) in your discord should hold the [bold]{}[/] role? [bright_black]Optional:[/]: An in-game chat replication. [green]- Database user and database created.[/] [red]A configuration for this nodes exists already![/]
Do you want to overwrite it? [red]Master password wrong. Please try again.[/] [red]No PostgreSQL-database found on {host}:{port}![/] [red]SRS configuration could not be created.
Please copy your server.cfg to {} manually.[/] [red]Wrong password! Try again.[/] [red]You need to give DCSServerBot write permissions on {} to desanitize your MissionScripting.lua![/] [yellow]Configuration found, adding another node...[/] [yellow]Existing {} user found![/] {} written Project-Id-Version: 1.0
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
Language: de
 

Alles erledigt. Schreibe die Konfiguration... 
1. Allgemeine Konfiguration 
2. Discord-Konfiguration 
Abgebrochen. 
DCS-Server "{}" gefunden.
Möchtest Du diesen Server zukünftig über DCSServerBot verwalten? 
Für eine erfolgreiche Installation musst Du die folgenden Voraussetzungen erfüllen:

    1. Installation der PostgreSQL-Datenbank von https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
    2. Ein Discord-TOKEN für Deinen Bot von https://discord.com/developers/applications

 
Bitte gebe die Kanal-ID für den Audit-Kanal an (optional) 
Suche DCS-World Installationen ... 
Der Statuskanal sollte für jeden lesbar und nur vom Bot beschreibbar sein.
Der Chat-Kanal sollte für jeden lesbar und beschreibbar sein.
Der Admin-Kanal - ob zentral oder nicht - sollte nur von Admin und DCS Admin lesbar und beschreibbar sein.

Du kannst diese Kanäle jetzt erstellen, da ich gleich nach den IDs fragen werde.
DCSServerBot benötigt die folgenden Berechtigungen auf all diesen Kanälen:

    - View Channel
    - Send Messages
    - Read Messages
    - Read Message History
    - Add Reactions
    - Attach Files
    - Embed Links
    - Manage Messages

 
Der Bot kann entweder einen zentralen Admin-Kanal nutzen, oder einen Admin-Kanal für jeden zu verwaltenden Server.
Wenn Du einen zentralen Admin-Kanal nutzen möchtest, bitte gebe die ID an (optional) 
Nun erstellen wir das Discord-Rollen-Mapping und die Discord-Kanäle.
DCSServerBot hat ein eigenes Rollen-Mapping. Es gibt die folgenden internen Rollen: 
[green]Deine DCSServerBot-Konfiguration ist abgeschlossen.[/]

Du kannst nun die erstellten Konfigurationsdateien im config-Ordner der DCSServerBot-Installation überprüfen.
Es gibt noch viel mehr zu entdecken und zu konfigurieren, also vergesse bitte nicht, einen Blick auf die Dokumentation zu werfen!

So kannst Du DCSServerBot starten:

    [bright_black]run.cmd[/]

 
{}. DCS-Server-Konfiguration 
{}. Datenbank-Konfiguration 
{}. Knoten-Konfiguration - {} erzeugt Abgebrochen. Keine DCS-Installation gefunden. Abgebrochen. Keine gültige Datenbank-URL angegeben. Abgebrochen. Diese Konfiguration existiert bereits. Abgebrochen. Voraussetzungen nicht erfüllt. Füge Instanz {instance} mit dem Server {name} hinzu ... DCS-SRS Installations-Verzeichnis: {} DCS-SRS wurde nicht konfiguriert. Du kannst bis zu {} Discord-Kanäle pro DCS-Server anlegen: Verzeichnis nicht gefunden. Bitte versuche es noch einmal. Erinnerst Du Dich an das Passwort von {}? Möchtest Du, dass DCSServerBot diesen DCS-Server automatisch startet? Möchtest Du DCS vom Bot automatisch aktualisieren lassen? Möchtest Du Deinen Bot automatisch updaten lassen? Bitte gebe den Hostnamen des PostgreSQL-Datenbankservers an Bitte gebe den Datenbank-Port an Für Admin-Kommandos. Hast Du diese Voraussetzungen erfüllt? Ich habe mehrere DCS-Installationen auf diesem PC gefunden: Installation abgeschlossen. Instanz {} konfiguriert. Keine konfigurierten DCS-Server gefunden. Normale Benutzerrolle, kann Statistiken aufrufen, ATIS, etc. Andere Bitte gib die ID des [bold]Admin-Kanals[/] ein Bitte gib die ID des [bold]Chat-Kanals[/] ein (optional) Bitte gib die ID des [bold]Status-Kanals[/] ein Bitte gebe den Pfad zu Deiner DCS World Installation an Bitte gib den Pfad zur DCS-SRS-Installation ein.
Drücke auf ENTER, wenn Du kein SRS installiert hast. Bitte gebe Deine "Guild ID" ein (rechts-klick auf den Discord-Server, "Copy Server ID") Bitte gebe die Benutzer-ID an (rechts-klick auf Deinen Discord-Benutzer "Copy User ID") Bitte gebe das Passwort für den postgres-Benutzer ein Bitte gebe Deinen Discord-TOKEN ein (s. Dokumentation) Bitte gebe des Passwort für den Benutzer {} ein Bitte separiere mehrere Rollen mit Kommas, falls notwendig.
Du kannst auch den Standard beibehalten, musst dann aber die entsprechenden Rollen in Discord anlegen. Bitte gebe an, welche Installation Du für den Bot nutzen möchtest SRS-Konfiguration konnte nicht erzeugt werden, manuelle Konfiguration notwendig. Der Bot kann alle Nachrichten in Discord oder DCS auch in dieser Sprache ausgeben. Möchtest Du das? Zeigt den Status des DCS-Servers und die aktuelle Spieler-Liste an Benutzer können bspw. alle Daten löschen, den Bot verändern oder sogar Kommandos auf dem PC ausführen. Benutzer können bspw. Missionen hochladen, DCS-Server starten und stoppen sowie Nutzer kicken und bannen. Welche Rolle(n) möchtest Du auf die [bold]{}[/]-Rolle mappen? [bright_black]Optional:[/]: Repliziert die Chatnachrichten aus DCS. [green]- Datenbank-Benutzer und Datenbank erzeugt.[/] [red]Für diesen Knoten gibt es bereits eine Konfiguration!![/]
Möchtest Du sie überschreiben? [red]Falsches Passwort für den Benutzer "postgres". Bitte versuche es erneut.[/] [red]Keine PostgreSQL-Datenbank auf {host}:{port} gefunden![/] [red]SRS-Konfiguration konnte nicht erzeugt werden.
Bitte kopiere Deine server.cfg manuell nach {}.[/] [red]Falsches Passwort! Bitte probiere es erneut.[/] [red]Du musst DCSServerBot Schreibrechte auf {} geben, um die MissionScripting.lua desanitisieren zu können![/] [yellow]Konfiguration vorhanden, füge einen weiteren Knoten hinzu...[/] [yellow]Der Benutzer {} existiert bereits![/] {} geschrieben 