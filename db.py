import asyncio
import json
import aiomysql
import typing as t

from itertools import chain
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
    `notified_maps` MEDIUMTEXT NOT NULL , 
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""
SERVER_INFO = """"
CREATE TABLE `not1x`.`server_info` ( 
    `id` INT NOT NULL AUTO_INCREMENT , 
    `tracking_ip` VARCHAR(1024) NOT NULL , 
    `maphistory` LONGTEXT NOT NULL ,
    PRIMARY KEY (`id`)
) ENGINE = InnoDB;
"""


class connection:
    def __init__(self, connection: aiomysql.Connection, cursor: aiomysql.Cursor) -> None:
        self.connection = connection
        self.cursor = cursor

    @classmethod
    async def conn(cls):
        with open("_debugs/config.json", "r") as cfg:
            data = json.load(cfg)
            data = data["database"]
        try:
            _conn: aiomysql.Connection = await aiomysql.connect(
                host=data["host"],
                port=data["port"],
                user=data["user"],
                password=data["password"],
                db=data["db"],
            )
        except Exception as e:
            _logger.critical("Failed to connect to database")
            raise e
        else:
            _cursor: aiomysql.Cursor = await _conn.cursor()
            return cls(_conn, _cursor)


async def getnotify(userid: int) -> list:
    db = await connection.conn()
    await db.cursor.execute("SELECT notified_maps FROM user_data WHERE userid = %s", (userid))
    r = await db.cursor.fetchone()
    db.connection.close()
    return [m for m in r[0].split(",")] if r and len(r[0]) > 1 else []


async def insertnotify(userid: int, name: str, maps: t.List[str], *, delete: bool = False):
    sep_maps = ",".join(maps)
    db = await connection.conn()
    await db.cursor.execute("SELECT userid FROM user_data WHERE userid = %s", (userid))
    r = await db.cursor.fetchone()
    if r:
        existed_notification = await getnotify(userid)
        if not delete:
            _maps = [a for a in maps if a not in existed_notification]
            _maps.extend(existed_notification)
        else:
            _maps = [a for a in existed_notification if a not in maps]
        sep_maps = ",".join(sorted(_maps))
        await db.cursor.execute(
            "UPDATE `user_data` SET `notified_maps`= %s WHERE userid = %s",
            (
                str(sep_maps),
                str(userid),
            ),
        )
        _logger.info(f"Successfully updated notify for {name}")
    else:
        await db.cursor.execute(
            "INSERT INTO `user_data`(`userid`, `name`, `notified_maps`) VALUES (%s, %s, %s)",
            (str(userid), str(name), str(sep_maps)),
        )
        _logger.info(f"Successfully added new user {name} to db")
    await db.connection.commit()
    db.connection.close()


async def fetchuser() -> tuple:
    db = await connection.conn()
    await db.cursor.execute("SELECT * FROM `user_data`")
    r = await db.cursor.fetchall()
    db.connection.close()
    return r


async def fetchguild() -> tuple:
    db = await connection.conn()
    await db.cursor.execute("SELECT * FROM `guild_tracking`")
    r = await db.cursor.fetchall()
    db.connection.close()
    return r


async def fetchip(ip: str):
    db = await connection.conn()
    await db.cursor.execute("SELECT * FROM `guild_tracking` WHERE `tracking_ip` = %s", (ip))
    r = await db.cursor.fetchall()
    db.connection.close()
    return r


async def loadguild(id: int):
    db = await connection.conn()
    await db.cursor.execute("SELECT `guild_id` FROM `guild_tracking`")
    result = await db.cursor.fetchall()
    if id in [r[0] for r in list(result)]:
        pass
    else:
        await db.cursor.execute(
            "INSERT INTO `guild_tracking`(`guild_id`) VALUES (%s)",
            (str(id)),
        )
        _logger.info(f"Successfully added new guild {id} to db")
        await db.connection.commit()
    db.connection.close()


async def getchannel(guild: int) -> int:
    db = await connection.conn()
    await db.cursor.execute("SELECT `channel_id` FROM `guild_tracking` WHERE guild_id = %s", (guild))
    r = await db.cursor.fetchone()
    return r[0] if r else 0


async def updatechannel(guild: int, channel: int):
    db = await connection.conn()
    await db.cursor.execute(
        "UPDATE `guild_tracking` SET `channel_id`= %s WHERE guild_id = %s",
        (channel, guild),
    )
    await db.connection.commit()
    db.connection.close()


async def updatetracking(guild: int, ip: str, msg_id: int):
    db = await connection.conn()
    await db.cursor.execute(
        "UPDATE `guild_tracking` SET `message_id`= %s WHERE `guild_id` = %s AND `tracking_ip` = %s",
        (msg_id, guild, ip),
    )
    await db.connection.commit()
    db.connection.close()


async def inserttracking(guild_id: int, channel_id: int, tracking_ip: str, message_id: int):
    db = await connection.conn()
    await db.cursor.execute(
        "INSERT INTO `guild_tracking`(`guild_id`, `channel_id`, `tracking_ip`, `message_id`) VALUES (%s, %s, %s, %s)",
        (guild_id, channel_id, tracking_ip, message_id),
    )
    await db.connection.commit()
    db.connection.close()


async def gettracking(guild: int, ip: str = None) -> list:
    db = await connection.conn()
    if ip:
        await db.cursor.execute(
            "SELECT `tracking_ip` FROM `guild_tracking` WHERE `guild_id` = %s AND `tracking_ip` = %s",
            (guild, ip),
        )
    else:
        await db.cursor.execute("SELECT `tracking_ip` FROM `guild_tracking` WHERE `guild_id` = %s", (guild))

    r = await db.cursor.fetchall()
    rs = list(chain.from_iterable(r))
    return [_r for _r in rs if _r != "0"] if r else []


async def updateserver(ip: str, map_history: dict):
    db = await connection.conn()
    await db.cursor.execute("SELECT `maphistory` FROM `server_info` WHERE `tracking_ip` = %s", (ip))
    r = await db.cursor.fetchone()
    if not r:
        q = "INSERT INTO `server_info`(`tracking_ip`, `maphistory`) VALUES (%s, %s)"
        await db.cursor.execute(q, (ip, map_history))
    else:
        _history = json.loads(r[0].replace("'", '"')) if r[0] else {}
        _history.popitem


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


if __name__ == "__main__":  # for debug/testing
    dd = {"serverip": "dsadwdsawdsaw", "aserverip": "dsadwdsawdsaw"}

    async def test():
        db = await connection.conn()
        await db.cursor.execute(
            "SELECT `tracking_ip` FROM `guild_tracking` WHERE `guild_id` = %s AND `tracking_ip` = %s",
            ("620983321677004800", "216.52.148.47:27015"),
        )
        r = db.cursor.fetchall()
        print(r)

    asyncio.run(test())
