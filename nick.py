import os
import re
import ffmpeg
import requests
import xml.etree.ElementTree as ET

MGID = "mgid:arc:promotion:nick.com:0cdfdb4d-ab75-45a4-9ee0-a5ec3205c248"

class Episode:
	def __init__(self, show, item):
		self.show = show
		self.name = item["title"]
		self.mgid = item["mgid"]

	@staticmethod
	def _download_item(url, output):
		item = requests.get(url, params={
			"acceptMethods": "hls",
			"format": "json",
		}).json()["package"]["video"]["item"][0]
		src = item["rendition"][-1]["src"]
		if "transcript" in item:
			subtitles = next(i for i in item["transcript"][0]["typographic"] if i["format"] == "ttml")
			with open(output + ".ttml", "w", encoding="utf-8") as file:
				file.write(requests.get(subtitles["src"]).text)
		sizes = re.findall(r"(,stream_(\d+)x(\d+)(?:_\d+)+)", src)
		size = max(sizes, key=lambda x: int(x[2]))
		src = re.sub(r",stream_[^/]+", size[0], src)
		ffmpeg.input(src).output(output + ".mp4", vcodec="copy").run()

	def download(self):
		name = self.name.replace("/", " ")
		if '"' in name:
			name = name[name.index('"') + 1:name.rindex('"')]
		dirname = os.path.join(self.show.name, name)
		if not os.path.isdir(dirname):
			os.makedirs(dirname)
		root = ET.fromstring(requests.get("http://udat.mtvnservices.com/service1/dispatch.htm", params={
			"feed": "nick_arc_player_prime",
			"mgid": self.mgid,
		}).text)
		namespace = {"media": "http://search.yahoo.com/mrss/"}
		for item in root.findall(".//item"):
			url = item.find("media:group/media:content", namespace).get("url")
			title = item.find("media:group/media:title", namespace).text.replace("/", " ").replace(":", " ").strip()
			if '"' in title:
				title = title[title.index('"') + 1:title.rindex('"')] + title[title.rindex('"') + 1:]
			self._download_item(url, os.path.join(dirname, title))

	def __str__(self):
		return self.name

class Show:
	def __init__(self, item):
		self.name = item["title"]
		self.links = item["links"]

	@classmethod
	def get_shows(cls, mgid):
		items = requests.get(f"http://api.playplex.viacom.com/feeds/networkapp/intl/promolist/1.9/{mgid}", params={
			"platform": "android",
			"brand": "nick",
			"version": "18.21.1",
			"region": "us",
			"key": "networkapp1.0",
		}).json()["data"]["items"]
		for item in items:
			if item["entityType"] == "series":
				yield cls(item)

	def get_episodes(self):
		items = requests.get(self.links["episode"]).json()["data"]["items"]
		for item in items:
			yield Episode(self, item)

	def __str__(self):
		return self.name

def choose(items, name):
	items = list(items)
	for i, item in enumerate(items, 1):
		print(f"{i}. {item}")
	return items[int(input(f"Which {name}? ")) - 1]

def main():
	show = choose(Show.get_shows(MGID), "show")
	episode = choose(show.get_episodes(), "episode")
	episode.download()

if __name__ == "__main__":
	main()