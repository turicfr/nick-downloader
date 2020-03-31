import os
import re
import json
import requests
import ffmpeg
import xml.etree.ElementTree as ET

def format_name(name, include_segment=False):
    name = re.sub(r"[<>:\/|?*]", " ", name)
    if '"' in name:
        quoted = name[name.index('"') + 1:name.rindex('"')]
        if include_segment:
            name = quoted + name[name.rindex('"') + 1:]
        else:
            name = quoted
    return " ".join(name.split())

class Episode:
    def __init__(self, data, series):
        self.data = data
        self.series = series

    @staticmethod
    def _download_item(url, output):
        item = requests.get(url, params={
            "deviceOsVersion": 10,
            "format": "json"
        }).json()["package"]["video"]["item"][0]
        src = item["rendition"][-1]["src"]
        if "transcript" in item:
            subtitles = next(i for i in item["transcript"][0]["typographic"] if i["format"] == "ttml")
            with open(f"{output}.ttml", "w", encoding="utf-8") as file:
                file.write(requests.get(subtitles["src"]).text)
        ffmpeg.input(src).output(f"{output}.mp4", vcodec="copy").overwrite_output().run()

    def download(self):
        dirname = os.path.join(self.series.name, format_name(self.name))
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        response = requests.get("http://media.mtvnservices.com/pmt/e1/access/", params={
            "uri": f'mgid:arc:episode:nickelodeonplay.com:{self.data["id"]}'
        }, headers={
            "Referer": f'http://media.mtvnservices.com/player/api/mobile/androidNative/nick_play_app.live.Android.{self.series.locale}/'
        }).json()
        root = ET.fromstring(requests.get(response["config"]["feed"].format(
            uri=f'mgid:arc:episode:nickelodeonplay.com:{self.data["id"]}',
            lang=self.series.lang,
        )).text)
        namespace = {"media": "http://search.yahoo.com/mrss/"}
        guid = root.find(".//guid", namespace).text
        for item in root.findall(".//item", namespace):
            guid = item.find("guid", namespace).text
            url = response["config"]["brightcove_mediagenRootURL"].format(
                uri=guid,
                device="Android",
                lang=self.series.lang,
            )
            title = format_name(item.find("title").text, True)
            self._download_item(url, os.path.join(dirname, title))

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.data["title"]

class Series:
    def __init__(self, data, lang, locale):
        self.data = data
        self.lang = lang
        self.locale = locale

    @classmethod
    def get_series(cls, lang, locale):
        items = requests.get("https://apinickvimn-a.akamaihd.net/api/v2/intl-editorial-content-categories/properties", params={
            "overridelang": True,
            "lang": lang,
            "locale": locale,
            "brand": "NickIntl",
            "platform": "App",
        }).json()
        for item in items:
            yield cls(item, lang, locale)

    def get_episodes(self):
        items = requests.get("https://apinickvimn-a.akamaihd.net/api/v2/content-collection/config/groups", params={
            "series": self.data["urlKey"],
            "types": "episode",
            "lang": self.lang,
            "locale": self.locale,
            "brand": "NickIntl",
            "platform": "App",
        }).json()["results"]
        for item in items:
            yield Episode(item, self)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.data["seriesTitle"]

def choose(items, name, to_string=None):
    items = list(items)
    if to_string is None:
        to_string = str
    for i, item in enumerate(items, 1):
        print(f"{f'{i}.'.ljust(3)} {to_string(item)}")
    return items[int(input(f"Which {name}? ")) - 1]

def main():
    with open(os.path.join(os.path.dirname(__file__), "regions.json")) as file:
        regions = json.load(file)
    region = choose(regions, "language", lambda r: r["name"])
    series = choose(Series.get_series(region["lang"], region["locale"]), "series")
    episode = choose(series.get_episodes(), "episode")
    episode.download()

if __name__ == "__main__":
    main()
