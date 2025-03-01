'''
* Copyright (C) 2019-2020 Intel Corporation.
*
* SPDX-License-Identifier: BSD-3-Clause
'''

import gi
gi.require_version('GstRtspServer', '1.0')
gi.require_version('Gst', '1.0')
# pylint: disable=wrong-import-position
from gi.repository import Gst, GstRtspServer
from vaserving.common.utils import logging
# pylint: enable=wrong-import-position

class GStreamerRtspFactory(GstRtspServer.RTSPMediaFactory):
    _source = "appsrc name=source format=GST_FORMAT_TIME"

    _RtspVideoPipeline = " ! videoconvert ! video/x-raw,format=I420 ! gvawatermark " \
    " ! jpegenc ! rtpjpegpay name=pay0 pt=96"

    # Decoding audio again as there is issue with audio pipeline element audiomixer
    _RtspAudioPipeline = " ! queue ! decodebin ! audioresample ! audioconvert " \
    " ! avenc_aac ! queue ! mpegtsmux ! rtpmp2tpay  name=pay0 pt=96"

    def __init__(self, rtsp_server):
        GstRtspServer.RTSPMediaFactory.__init__(self)
        self._logger = logging.get_logger(
            'GStreamerRtspFactory', is_static=True)
        self._rtsp_server = rtsp_server
        if not self._rtsp_server:
            self._logger.error("GStreamerRtspFactory: Invalid RTSP Server")
            raise Exception("GStreamerRtspFactory: Invalid RTSP Server")

    def _select_caps(self, caps):
        split_caps = caps.split(',')
        new_caps = []
        selected_caps = ['video/x-raw', 'width', 'height',
                         'audio/x-raw', 'rate', 'channels', 'layout',
                         'format']
        for cap in split_caps:
            for selected in selected_caps:
                if selected in cap:
                    new_caps.append(cap)
        return new_caps

    def do_create_element(self, url):
        # pylint: disable=arguments-differ
        # pylint disable added as pylint comparing do_create_element with some other method with same name.

        stream = self._rtsp_server.get_source(url.abspath)
        if not stream:
            self._logger.error(
                "GStreamerRtspFactory: Missing source for RTSP pipeline path {}".format(url.abspath))
            return None

        source = stream.source
        caps = stream.caps

        new_caps = self._select_caps(caps.to_string())
        s_src = "{} caps=\"{}\"".format(GStreamerRtspFactory._source, ','.join(new_caps))
        media_pipeline = GStreamerRtspFactory._RtspVideoPipeline
        is_audio_pipeline = False
        if caps.to_string().startswith('audio'):
            media_pipeline = GStreamerRtspFactory._RtspAudioPipeline
            is_audio_pipeline = True
        launch_string = " {} {} ".format(s_src, media_pipeline)
        self._logger.debug("Starting RTSP stream url:{}".format(url))
        self._logger.debug(launch_string)
        pipeline = Gst.parse_launch(launch_string)
        pipeline.caps = caps
        appsrc = pipeline.get_by_name("source")
        source.set_app_src(appsrc, is_audio_pipeline)
        appsrc.connect('need-data', source.on_need_data)
        appsrc.connect('enough-data', source.enough_data)
        return pipeline
