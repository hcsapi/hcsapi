import asyncio
import json
import sys
from base64 import b64decode, b64encode

import aiohttp
import jwt

from .mapping import encrypt, pubkey, schoolinfo
from .request import search_school, send_hcsreq, UIVersion
from .transkey import mTransKey


def selfcheck(user, customloginname: str = None, loop=asyncio.get_event_loop()):
    return loop.run_until_complete(
        asyncSelfCheck(user, customloginname)
    )


def changePassword(user, newpassword: str, loop=asyncio.get_event_loop()):
    return loop.run_until_complete(
        asyncChangePassword(user, newpassword)
    )


def userlogin(user, loop=asyncio.get_event_loop()):
    return loop.run_until_complete(
        asyncUserLogin(user, aiohttp.ClientSession())
    )


def generatetoken(user, loop=asyncio.get_event_loop()):
    return loop.run_until_complete(
        asyncGenerateToken(user)
    )


def tokenselfcheck(token: str, loop=asyncio.get_event_loop()):
    return loop.run_until_complete(asyncTokenSelfCheck(token))


async def asyncSelfCheck(user, customloginname: str = None):
    async with aiohttp.ClientSession() as session:
        if customloginname is None:
            customloginname = user.name

        login_result = await asyncUserLogin(user, session)

        if login_result["error"]:
            return login_result

        try:
            res = await send_hcsreq(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": login_result["token"],
                },
                endpoint="/v2/selectUserGroup",
                school=login_result["info"]["schoolurl"],
                json={},
                session=session,
            )
            userdataobject = {}
            for user in res:
                if user["otherYn"] == "N":
                    userdataobject = user
                    break

            userPNo = userdataobject["userPNo"]
            token = userdataobject["token"]

            res = await send_hcsreq(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
                },
                endpoint="/v2/getUserInfo",
                school=login_result["info"]["schoolurl"],
                json={"orgCode": login_result["schoolcode"], userPNo: userPNo},
                session=session,
            )

            token = res["token"]

        except Exception:
            return {
                "error": True,
                "code": "UNKNOWN",
                "message": "getUserInfo: 알 수 없는 에러 발생.",
            }

        try:
            #base payload
            jsonPayload = {
                        "clientVersion": UIVersion(),
                        "rspns00": "Y",
                        "rspns01": "1",
                        "rspns02": "1",
                        "upperToken": token,
                        "upperUserNameEncpt": customloginname,
                    }

            #selfcheck여부에 따른 payload 수정
            if user.selfcheck == "0" :
                jsonPayload["rspns03"] = "1";
            elif user.selfcheck == "1":
                jsonPayload["rspns07"] = "0";

            res = await send_hcsreq(
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": token,
                    },
                    endpoint="/registerServey",
                    school=login_result["info"]["schoolurl"],
                    json=jsonPayload,
                    session=session,
                )
            
            return {
                "error": False,
                "code": "SUCCESS",
                "message": "성공적으로 자가진단을 수행하였습니다.",
                "regtime": res["registerDtm"],
                "docheck": user.selfcheck,
            }

        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": "알 수 없는 에러 발생."}


async def asyncChangePassword(user, newpassword: str):
    async with aiohttp.ClientSession() as session:
        login_result = await asyncUserLogin(user, session)

        if login_result["error"]:
            return login_result

        try:
            res = await send_hcsreq(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": login_result["token"],
                },
                endpoint="/v2/changePassword",
                school=login_result["info"]["schoolurl"],
                json={
                    "password": encrypt(user.password),
                    "newPassword": encrypt(newpassword),
                },
                session=session,
            )

            if res:
                return {
                    "error": False,
                    "code": "SUCCESS",
                    "message": "성공적으로 비밀번호 변경에 성공하였습니다.",
                }

        except Exception:
            return {
                "error": True,
                "code": "INCORRECTPASSWORD",
                "message": "getUserInfo: 알 수 없는 에러 발생.",
            }


async def asyncUserLogin(user, session: aiohttp.ClientSession):
    name = encrypt(name)  # Encrypt Name
    birth = encrypt(birth)  # Encrypt Birth

    try:
        info = schoolinfo(user.region, user.level)  # Get schoolInfo from Hcs API

    except Exception:
        return {"error": True, "code": "FORMET", "message": "지역명이나 학교급을 잘못 입력하였습니다."}

    school_infos = await search_school(
        code=info["schoolcode"], level=info["schoollevel"], org=user.school
    )

    token = school_infos["key"]

    if len(school_infos["schulList"]) > 5:
        return {
            "error": True,
            "code": "NOSCHOOL",
            "message": "너무 많은 학교가 검색되었습니다. 지역, 학교급을 제대로 입력하고 학교 이름을 보다 상세하게 적어주세요.",
        }

    try:
        schoolcode = school_infos["schulList"][0]["orgCode"]

    except Exception:
        return {
            "error": True,
            "code": "NOSCHOOL",
            "message": "검색 가능한 학교가 없습니다. 지역, 학교급을 제대로 입력하였는지 확인해주세요.",
        }

    try:
        res = await send_hcsreq(
            headers={"Content-Type": "application/json"},
            endpoint="/v2/findUser",
            school=info["schoolurl"],
            json={
                "orgCode": schoolcode,
                "name": name,
                "birthday": birth,
                "loginType": "school",
                "searchKey": token,
                "stdntPNo": None,
            },
            session=session,
        )

        token = res["token"]

    except Exception:
        return {
            "error": True,
            "code": "NOSTUDENT",
            "message": "학교는 검색하였으나, 입력한 정보의 학생을 찾을 수 없습니다.",
        }

    try:
        mtk = mTransKey("https://hcs.eduro.go.kr/transkeyServlet")
        pw_pad = await mtk.new_keypad("number", "password", "password", "password")
        encrypted = pw_pad.encrypt_password(user.password)
        hm = mtk.hmac_digest(encrypted.encode())

        res = await send_hcsreq(
            headers={
                "Referer": "https://hcs.eduro.go.kr/",
                "Authorization": token,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json;charset=utf-8",
            },
            endpoint="/v2/validatePassword",
            school=info["schoolurl"],
            json={
                "password": json.dumps(
                    {
                        "raon": [
                            {
                                "id": "password",
                                "enc": encrypted,
                                "hmac": hm,
                                "keyboardType": "number",
                                "keyIndex": mtk.keyIndex,
                                "fieldType": "password",
                                "seedKey": mtk.crypto.get_encrypted_key(),
                                "initTime": mtk.initTime,
                                "ExE2E": "false",
                            }
                        ]
                    }
                ),
                "deviceUuid": "",
                "makeSession": True,
            },
            session=session,
        )

        if "isError" in res:
            return {
                "error": True,
                "code": "PASSWORD",
                "message": "학생정보는 검색하였으나, 비밀번호가 틀립니다.",
            }

        token = res["token"]

    except Exception as e:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": f"validatePassword: 알 수 없는 에러 발생. {e}",
        }

    try:
        caller_name = str(sys._getframe(1).f_code.co_name)

    except Exception:
        caller_name = None

    if caller_name == "asyncSelfCheck" or caller_name == "asyncChangePassword":
        return {
            "error": False,
            "code": "SUCCESS",
            "message": "유저 로그인 성공!",
            "token": token,
            "info": info,
            "schoolcode": schoolcode,
        }

    return {"error": False, "code": "SUCCESS", "message": "유저 로그인 성공!"}


async def asyncGenerateToken(user):
    async with aiohttp.ClientSession() as session:
        login_result = await asyncUserLogin(**locals())

        if login_result["error"]:
            return login_result

        data = {
            "name": str(user.name),
            "birth": str(user.birth),
            "area": str(user.region),
            "schoolname": str(user.school),
            "level": str(user.level),
            "password": str(user.password),
        }

        jwt_token = jwt.encode(data, pubkey, algorithm="HS256")

        if isinstance(jwt_token, str):
            jwt_token = jwt_token.encode("utf8")

        token = b64encode(jwt_token).decode("utf8")

        return {
            "error": False,
            "code": "SUCCESS",
            "message": "자가진단 토큰 발급 성공!",
            "token": token,
        }


async def asyncTokenSelfCheck(token: str, customloginname: str = None):
    try:
        data = jwt.decode(b64decode(token), pubkey, algorithms="HS256")

    except Exception:
        return {"error": True, "code": "WRONGTOKEN", "message": "올바르지 않은 토큰입니다."}

    return await asyncSelfCheck(
        data["name"],
        data["birth"],
        data["area"],
        data["schoolname"],
        data["level"],
        data["password"],
        customloginname,
    )
