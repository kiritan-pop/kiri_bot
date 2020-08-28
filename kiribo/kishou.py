# coding: utf-8
import os,sys,io,re,json
from socketIO_client_nexus import SocketIO, LoggingNamespace
import xmltodict
from collections import OrderedDict
import requests

from kiribo import util
logger = util.setup_logger(__name__)

class Kirikishou():
    def __init__(self, ws_url, ws_port=80, kishou_target={}, on_msg_func=None):
        self.ws_url = ws_url
        self.ws_port = ws_port
        self.kishou_target = kishou_target
        self.on_msg_func = on_msg_func

    def connect_run_forever(self):
        socketIO = SocketIO(self.ws_url, self.ws_port, LoggingNamespace)
        socketIO.on('connect', self._on_connect)
        socketIO.on('disconnect', self._on_disconnect)
        socketIO.on('reconnect', self._on_reconnect)
        socketIO.on('msg', self._on_msg)
        socketIO.wait()

    def _on_connect(self):
        logger.info('connect')

    def _on_disconnect(self):
        logger.info('disconnect')

    def _on_reconnect(self):
        logger.info('reconnect')

    def _on_msg(self, xml_data):
        logger.info('on_msg')
        try:
            doc = xmltodict.parse(xml_data)
            feeds = []
            # entryが１件の場合と複数の場合に分ける
            if isinstance(doc['feed']['entry'], list):
                for d in doc['feed']['entry']:
                    tmp_dict = {}
                    tmp_dict['title'] = d['title']
                    tmp_dict['link'] = d['link']['@href']
                    tmp_dict['content'] = d['content']['#text']
                    feeds.append(tmp_dict)
            elif isinstance(doc['feed']['entry'], OrderedDict):
                tmp_dict = {}
                tmp_dict['title'] = doc['feed']['entry']['title']
                tmp_dict['link'] = doc['feed']['entry']['link']['@href']
                tmp_dict['content'] = doc['feed']['entry']['content']['#text']
                feeds.append(tmp_dict)

            for feed in feeds:
                logger.info(f"title  :{feed['title']}" )
                logger.info(f"link   :{feed['link']}" )
                logger.info(f"content:{feed['content']}" )
                if feed['title'] in self.kishou_target:
                    res = requests.get(feed['link'])
                    main_doc = xmltodict.parse(res.content.decode("utf-8"))
                    if self.on_msg_func:
                        self.on_msg_func(main_doc)
                    else:
                        logger.error(main_doc)

        except Exception as e:
            logger.error(e)
