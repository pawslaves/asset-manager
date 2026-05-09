import os
import re
import json
import base64
from concurrent.futures import ThreadPoolExecutor as Pool
import requests as reqs
import urllib.parse
import xml.etree.ElementTree as ET

def clean(s):
    return "".join(c for c in s if c.isalnum() or c in " ._-").strip()

class Spoofer:
    def __init__(self):
        self.cfg = self._load_config()

    def _load_config(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _csrf(self, ses, ck, url="https://auth.roblox.com/v2/logout"):
        h = {"Cookie": f".ROBLOSECURITY={ck}"}
        r = ses.post(url, headers=h, timeout=10)
        return r.headers.get("x-csrf-token")

    def _quota(self, ses, ck):
        url = "https://publish.roblox.com/v1/asset-quotas?resourceType=RateLimitUpload&assetType=Audio"
        h = {"Cookie": f".ROBLOSECURITY={ck}", "User-Agent": "RobloxStudio/WinInet"}
        try:
            r = ses.get(url, headers=h, timeout=10)
            q = r.json()["quotas"][0]
            return q["capacity"] - q["usage"]
        except Exception:
            return 0

    def _places(self, ses, ck, ct, cid):
        url = f"https://games.roblox.com/v2/{'groups' if ct == 'Group' else 'users'}/{cid}/games?limit=10"
        h = {"Cookie": f".ROBLOSECURITY={ck}"}
        try:
            r = ses.get(url, headers=h, timeout=10)
            return [g["rootPlace"]["id"] for g in r.json()["data"] if g.get("rootPlace")]
        except Exception:
            return []

    def _meta(self, ses, aid, ck):
        url = f"https://economy.roblox.com/v2/assets/{aid}/details"
        h = {"Cookie": f".ROBLOSECURITY={ck}", "User-Agent": "RobloxStudio/WinInet"}
        try:
            r = ses.get(url, headers=h, timeout=10)
            d = r.json()
            return d.get("Creator", {}).get("CreatorType"), d.get("Creator", {}).get("CreatorTargetId")
        except Exception:
            return None, None

    def _download(self, ses, aid, ck, place_id):
        url = f"https://assetdelivery.roblox.com/v1/asset/?id={aid}"
        h = {"Cookie": f".ROBLOSECURITY={ck}", "User-Agent": "RobloxStudio/WinInet"}
        if place_id:
            h["Roblox-Place-Id"] = str(place_id)
        try:
            r = ses.get(url, headers=h, timeout=20)
            if r.status_code == 200:
                return r.content, None
            return None, r.status_code
        except Exception:
            return None, "err"

    def _upload_animation(self, ses, name, data, ck, token):
        params = {
            "assetTypeName": "Animation",
            "name": name,
            "description": "placeholder",
            "ispublic": "false",
            "allowComments": "true",
            "isGamesAsset": "false"
        }
        query = urllib.parse.urlencode(params)
        url = f"https://www.roblox.com/ide/publish/uploadnewanimation?{query}"
        h = {
            "Cookie": f".ROBLOSECURITY={ck}",
            "X-CSRF-TOKEN": token,
            "Content-Type": "application/octet-stream",
            "User-Agent": "RobloxStudio/WinInet"
        }
        r = ses.post(url, headers=h, data=data, timeout=25)
        if r.status_code == 403:
            ncs = r.headers.get("x-csrf-token")
            if ncs:
                h["X-CSRF-TOKEN"] = ncs
                r = ses.post(url, headers=h, data=data, timeout=25)
        t = r.text.strip()
        if r.status_code == 200 and t.isdigit():
            return t, None
        return None, f"http {r.status_code}"

    def _upload_audio(self, ses, name, data, ck, token):
        url = "https://publish.roblox.com/v1/audio"
        payload = {
            "name": name,
            "file": base64.b64encode(data).decode("utf-8"),
            "assetPrivacy": 1,
            "estimatedFileSize": len(data),
            "estimatedDuration": 0,
            "paymentSource": "User"
        }
        h = {
            "Cookie": f".ROBLOSECURITY={ck}",
            "x-csrf-token": token,
            "User-Agent": "RobloxStudio/WinInet",
            "Content-Type": "application/json"
        }
        r = ses.post(url, headers=h, json=payload, timeout=30)
        if r.status_code == 403:
            ncs = r.headers.get("x-csrf-token")
            if ncs:
                h["x-csrf-token"] = ncs
                r = ses.post(url, headers=h, json=payload, timeout=30)
        if r.status_code == 200:
            return str(r.json().get("Id", "")), None
        return None, f"http {r.status_code}"

    def _job(self, ses, old_id, kind, ck, token, place_id):
        data, code = self._download(ses, old_id, ck, place_id)
        if code == 403:
            ct, cid = self._meta(ses, old_id, ck)
            if cid:
                places = self._places(ses, ck, ct, cid)
                for p in places + [99840799534728]:
                    data, code = self._download(ses, old_id, ck, p)
                    if data:
                        break
        if not data:
            return old_id, None, f"dl {code}"

        upload_fn = self._upload_animation if kind == "Animation" else self._upload_audio
        name = f"s_{old_id}"
        result, err = upload_fn(ses, name, data, ck, token)
        return old_id, result, err

    def dump(self, path, cb):
        if not path.lower().endswith(".rbxlx"):
            return False, "must be .rbxlx"
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            dump_dir = "dump"
            os.makedirs(dump_dir, exist_ok=True)

            item_map = {c: p for p in root.iter() for c in p}
            items = [i for i in root.iter("Item") if i.get("class") in ["Script", "LocalScript", "ModuleScript"]]

            for i, it in enumerate(items):
                kind = it.get("class")
                props = it.find("Properties")
                if props is None:
                    continue

                name, src = "unknown", ""
                for p in props:
                    k = p.get("name")
                    if k == "Name":
                        name = p.text
                    elif k == "Source":
                        src = p.text or ""

                stack = []
                curr = it
                while curr is not None and curr.tag == "Item":
                    ps = curr.find("Properties")
                    tag = "unknown"
                    if ps is not None:
                        for p in ps:
                            if p.get("name") == "Name":
                                tag = p.text
                                break
                    stack.insert(0, clean(tag))
                    curr = item_map.get(curr)

                if not stack:
                    continue

                loc = os.path.join(dump_dir, *stack[:-1])
                os.makedirs(loc, exist_ok=True)

                ext_map = {"LocalScript": ".client.lua", "ModuleScript": ".lua", "Script": ".server.lua"}
                ext = ext_map.get(kind, ".lua")
                out_path = os.path.join(loc, f"{stack[-1]}{ext}")

                if "Server Scripts are IMPOSSIBLE to save" in src:
                    cb(i + 1, len(items), name, "skip")
                    continue

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(src)
                cb(i + 1, len(items), name, "saved")

            return True, "done"
        except Exception as e:
            return False, str(e)

    def _grab_ids(self, root):
        ids = {}
        for el in root.iter("Content"):
            n = el.get("name")
            if n in ["AnimationId", "SoundId"]:
                for v in el.iter("url"):
                    if v.text:
                        h = re.search(r"\d+", v.text)
                        if h:
                            ids[h.group()] = "Audio" if n == "SoundId" else "Animation"
        return ids

    def reup(self, path, mode, cb):
        if not path.lower().endswith(".rbxlx"):
            return False, "must be .rbxlx"

        cookies = self.cfg.get("cookies", [])
        place_id = self.cfg.get("placeId")
        if not cookies:
            return False, "no cookies"

        try:
            tree = ET.parse(path)
            root = tree.getroot()
            all_ids = self._grab_ids(root)

            if mode == "audio":
                todo = {o: k for o, k in all_ids.items() if k == "Audio"}
            elif mode == "animation":
                todo = {o: k for o, k in all_ids.items() if k == "Animation"}
            else:
                todo = all_ids

            if not todo:
                return True, "empty"

            sessions = []
            for ck in cookies:
                s = reqs.Session()
                sessions.append({
                    "ses": s,
                    "ck": ck,
                    "q": self._quota(s, ck),
                    "an": self._csrf(s, ck),
                    "au": self._csrf(s, ck, "https://publish.roblox.com/v1/audio")
                })

            work = []
            cur_audio = 0
            for old_id, kind in todo.items():
                if kind == "Audio":
                    while cur_audio < len(sessions) and sessions[cur_audio]["q"] <= 0:
                        cur_audio += 1
                    if cur_audio >= len(sessions):
                        continue
                    acc = sessions[cur_audio]
                    acc["q"] -= 1
                    work.append((old_id, kind, acc))
                else:
                    work.append((old_id, kind, sessions[0]))

            done = {}
            if work:
                with Pool(max_workers=5) as ex:
                    futures = [ex.submit(self._job, a["ses"], o, k, a["ck"],
                                        a["au"] if k == "Audio" else a["an"], place_id)
                              for o, k, a in work]
                    for i, f in enumerate(futures):
                        old, new, err = f.result()
                        if new:
                            done[old] = new
                        cb(i + 1, len(work), old, new or err)

            for el in root.iter("Content"):
                if el.get("name") in ["AnimationId", "SoundId"]:
                    for v in el.iter("url"):
                        if v.text:
                            for old, new in done.items():
                                v.text = v.text.replace(old, new)

            out = path.replace(".rbxlx", "_s.rbxlx")
            tree.write(out, encoding="utf-8", xml_declaration=True)
            return True, f"saved: {os.path.basename(out)}"
        except Exception as e:
            return False, str(e)
