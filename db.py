import asyncio
import json
import typing as t
from datetime import datetime
from ipaddress import IPv4Address
from itertools import chain

import aiomysql
import numpy as np
from pymysql.err import InterfaceError, OperationalError

from enums import MapEnum
from logs import setlog

_logger = setlog(__name__)


GUILD_TABLE = """
CREATE TABLE `not1x`.`guild_tracking` ( 
    `id` INT NOT NULL AUTO_INCREMENT , 
    `guild_id` BIGINT NOT NULL , 
    `channel_id` BIGINT NOT NULL DEFAULT '0' , 
    `tracking_ip` VARCHAR NOT NULL DEFAULT '0' , 
    `message_id` BIGINT NOT NULL DEFAULT '0' , 
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""
USER_TABLE = """
CREATE TABLE `not1x`.`user_data` ( 
    `id` INT NOT NULL AUTO_INCREMENT , 
    `userid` BIGINT NOT NULL , 
    `name` VARCHAR(1024) NOT NULL , 
    `notified_maps` VARCHAR NOT NULL , 
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""
SERVER_INFO = """"
CREATE TABLE `not1x`.`server_info` ( 
    `id` INT NOT NULL AUTO_INCREMENT , 
    `tracking_ip` VARCHAR NOT NULL , 
    `map` VARCHAR NOT NULL , 
    `date` DATE NOT NULL , 
    `lastplayed` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP , 
    `playtime` INT NOT NULL , 
    `played` INT NOT NULL , 
    `average_players` INT NOT NULL , 
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""
SERVER_DATA = """
CREATE TABLE `not1x`.`server_data` ( 
    `id` INT NOT NULL AUTO_INCREMENT , 
    `server_ip` VARCHAR(255) NOT NULL , 
    `last_map` VARCHAR(255) NOT NULL , 
    `time_play` BIGINT NOT NULL , 
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""
loop = asyncio.get_event_loop()


class iterdb:
    def __init__(self, data=t.Union[list, tuple]) -> None:
        self.count = 0
        self.data = data

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.count >= len(self.data):
            raise StopAsyncIteration
        iter = self.data[self.count]
        self.count += 1
        return iter


class connection:
    def __init__(self, data: dict) -> None:
        self.__data = data

    async def execute(
        self, query: str, *args, fetch: bool = False, fetchall: bool = False, res: bool = True, commit: bool = False
    ) -> t.Tuple | None:
        _res = None
        try:
            con: aiomysql.Connection = await aiomysql.connect(
                host=self.__data["host"],
                port=self.__data["port"],
                user=self.__data["user"],
                password=self.__data["password"],
                db=self.__data["db"],
            )
        except OperationalError:
            _logger.critical("Failed to connect to db!")
        except InterfaceError:
            _logger.critical("Connection to db was closed!")
        else:
            cursor: aiomysql.Cursor = await con.cursor()
            await cursor.execute(query, *args)
            if fetch:
                if fetchall:
                    _res = await cursor.fetchall()
                else:
                    _res = await cursor.fetchone()
            if commit:
                await con.commit()
            if res:
                con.close()
                return _res
            con.close()
        return _res

    async def getnotify(self, userid: int) -> t.List[str]:
        r = await self.execute(
            "SELECT notified_maps FROM user_data WHERE userid = %s", (userid), fetch=True, fetchall=True, res=True
        )
        return list(chain.from_iterable(r)) if r else []

    async def insertnotify(self, userid: int, name: str, maps: t.List[str], *, delete: bool = False):
        r = await self.execute(
            "SELECT userid FROM user_data WHERE userid = %s", (userid), fetch=True, fetchall=False, res=True
        )
        if r:
            async for map in iterdb(maps):
                if delete:
                    await self.execute(
                        "DELETE FROM `user_data` WHERE `notified_maps` = %s AND `userid` = %s",
                        (str(map), str(userid)),
                        commit=True,
                        res=False,
                        fetch=False,
                    )
                else:
                    await self.execute(
                        "INSERT INTO `user_data`(`userid`, `name`, `notified_maps`) VALUES (%s, %s, %s)",
                        (str(userid), str(name), str(map)),
                        commit=True,
                        res=False,
                        fetch=False,
                    )
            _logger.info(f"Successfully updated notify for {name}")
        else:
            async for map in iterdb(maps):
                await self.execute(
                    "INSERT INTO `user_data`(`userid`, `name`, `notified_maps`) VALUES (%s, %s, %s)",
                    (str(userid), str(name), str(map)),
                    commit=True,
                    res=False,
                    fetch=False,
                )
            _logger.info(f"Successfully added new user {name} to db")

    async def fetchuser(self) -> iterdb:
        r = await self.execute("SELECT * FROM `user_data`", fetch=True, fetchall=True, res=True)
        return iterdb(r)

    async def fetchuserid(self) -> iterdb:
        r = await self.execute("SELECT `userid` FROM `user_data`", fetch=True, fetchall=True, res=True)
        return iterdb(np.unique(r))

    async def fetchguild(self) -> tuple:
        r = await self.execute("SELECT * FROM `guild_tracking`", fetch=True, fetchall=True, res=True)
        return r

    async def fetchip(self, ip: str):
        r = await self.execute(
            "SELECT * FROM `guild_tracking` WHERE `tracking_ip` = %s", (ip), fetch=True, fetchall=True, res=True
        )
        return iterdb(r)

    async def loadguild(self, id: int):
        result = await self.execute("SELECT `guild_id` FROM `guild_tracking`", fetch=True, fetchall=True, res=True)
        if id in list(chain.from_iterable(result)):
            pass
        else:
            await self.execute(
                "INSERT INTO `guild_tracking`(`guild_id`) VALUES (%s)", (str(id)), commit=True, res=False, fetch=False
            )
            _logger.info(f"Successfully added new guild {id} to db")

    async def getchannel(self, guild: int) -> int:
        r = await self.execute(
            "SELECT `channel_id` FROM `guild_tracking` WHERE guild_id = %s",
            (guild),
            fetch=True,
            fetchall=False,
            res=True,
        )
        return r[0] if r else 0

    async def updatechannel(self, guild: int, channel: int):
        await self.execute(
            "UPDATE `guild_tracking` SET `channel_id`= %s WHERE guild_id = %s",
            (channel, guild),
            commit=True,
            fetch=False,
        )

    async def updatetracking(self, guild: int, ip: str, msg_id: int):
        await self.execute(
            "UPDATE `guild_tracking` SET `message_id`= %s WHERE `guild_id` = %s AND `tracking_ip` = %s",
            (msg_id, guild, ip),
            commit=True,
            fetch=False,
        )

    async def inserttracking(self, guild_id: int, channel_id: int, tracking_ip: str, message_id: int):
        await self.execute(
            "INSERT INTO `guild_tracking`(`guild_id`, `channel_id`, `tracking_ip`, `message_id`) VALUES (%s, %s, %s, %s)",
            (guild_id, channel_id, tracking_ip, message_id),
            commit=True,
        )

    async def deletetracking(self, guild_id: int, tracking_ip: str):
        await self.execute(
            "DELETE FROM `guild_tracking` WHERE `guild_id` = %s AND `tracking_ip` = %s",
            (guild_id, tracking_ip),
            commit=True,
        )

    async def gettracking(self, guild: int, ip: str = None) -> t.List[IPv4Address]:
        if ip:
            r = await self.execute(
                "SELECT `tracking_ip` FROM `guild_tracking` WHERE `guild_id` = %s AND `tracking_ip` = %s",
                (guild, ip),
                fetch=True,
                fetchall=True,
            )
        else:
            r = await self.execute(
                "SELECT `tracking_ip` FROM `guild_tracking` WHERE `guild_id` = %s", (guild), fetch=True, fetchall=True
            )
        rs = list(chain.from_iterable(r))
        return [_r for _r in rs if _r != "0"] if r else []

    async def updateserver(self, ip: str, map: str, date: datetime, playtime: int = 0, average_players: int = 0):
        q = "INSERT INTO `server_info` (`tracking_ip`, `map`, `date`, `playtime`, `played`, `average_players`) VALUES (%s, %s, %s, %s, %s, %s)"
        await self.execute(q, (ip, map, date, playtime, 1, average_players), commit=True)

    async def updatemaptime(self, ip: str, map: str, date: datetime, playtime: int = 0):
        q = "UPDATE `server_info` SET `playtime` = %s WHERE `tracking_ip` = %s AND `map` = %s AND `date` = %s"
        await self.execute(q, (playtime, ip, map, date), commit=True)

    async def updatelastmap(self, ip: str, newmap: str, timeplay: int):
        r = await self.execute(
            "SELECT `last_map` from `server_data` WHERE `server_ip` = %s", (ip), fetch=True, fetchall=True
        )
        if r:
            q = "UPDATE `server_data` SET `last_map` = %s, `time_play` = %s WHERE `server_ip` = %s"
            await self.execute(q, (newmap, timeplay, ip), commit=True)
        else:
            q = "INSERT INTO `server_data` (`server_ip`, `last_map`, `time_play`) VALUES (%s, %s, %s)"
            await self.execute(q, (ip, newmap, timeplay), commit=True)

    async def getlastmaptime(self, ip: str):
        r = await self.execute(
            "SELECT `time_play` FROM `server_data` WHERE `server_ip` = %s",
            (ip),
            fetch=True,
            fetchall=True,
            res=True,
            commit=False,
        )
        return list(chain.from_iterable(r))[0] if r else datetime.now().timestamp()

    async def updateplayers(self, ip: str, map: str, date: datetime, player: int):
        q = "UPDATE `server_info` SET `average_players` = %s WHERE `tracking_ip` = %s AND `map` = %s AND `date` = %s"
        await self.execute(q, (player, ip, map, date), commit=True)

    async def getserverdata(self):
        r = await self.execute("SELECT * FROM `server_info`", fetch=True, fetchall=True)
        return r

    async def fetchserverdata(self, ip: str) -> t.List[t.Tuple[int, str, str, datetime, datetime, int, int, float]]:
        """
        fetch server data from db
            return tuple(id, ip, map, date, lastplayed, playtime, played, average_players)
        """
        r = await self.execute("SELECT * FROM `server_info` WHERE `tracking_ip` = %s", (ip), fetch=True, fetchall=True)
        return r

    async def getlastmap(self, ip: str) -> t.Union[str, MapEnum.UNKOWN.value]:
        r = await self.execute(
            "SELECT `last_map` FROM `server_data` WHERE `server_ip` = %s",
            (ip),
            fetch=True,
            fetchall=True,
            res=True,
            commit=False,
        )
        return list(chain.from_iterable(r))[0] if r else MapEnum.UNKOWN
