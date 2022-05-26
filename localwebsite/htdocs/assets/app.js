(function() {
var RE_WHITESPACE = /[\t\r\n\f]/g

window.ajax = {
    get: function(url, data) {
        if (typeof data == 'object') {
            var index = 0;
            for (var key in data) {
                var val = data[key];
                url += index === 0 && url.indexOf('?') === -1 ? '?' : '&';
                url += encodeURIComponent(key) + '=' + encodeURIComponent(val);
            }
        }
        return this.raw(url);
    },

    post: function(url, body) {
        var opts = {
            method: 'POST'
        };
        if (body)
            opts.body = body;
        return this.raw(url, opts);
    },

    raw: function(url, options) {
        if (!options)
            options = {}

        return fetch(url, Object.assign({
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        }, options))
        .then(resp => {
            return resp.json()
        })
    }
};

window.extend = function(a, b) {
    return Object.assign(a, b);
}

window.ge = function(id) {
    return document.getElementById(id);
}

var ua = navigator.userAgent.toLowerCase();
window.browserInfo = {
    version: (ua.match(/.+(?:me|ox|on|rv|it|ra|ie)[\/: ]([\d.]+)/) || [0,'0'])[1],
    //opera: /opera/i.test(ua),
    msie: (/msie/i.test(ua) && !/opera/i.test(ua)) || /trident/i.test(ua),
    mozilla: /firefox/i.test(ua),
    android: /android/i.test(ua),
    mac: /mac/i.test(ua),
    samsungBrowser: /samsungbrowser/i.test(ua),
    chrome: /chrome/i.test(ua),
    safari: /safari/i.test(ua),
    mobile: /iphone|ipod|ipad|opera mini|opera mobi|iemobile|android/i.test(ua),
    operaMini: /opera mini/i.test(ua),
    ios: /iphone|ipod|ipad|watchos/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1),
};

window.isTouchDevice = function() {
    return 'ontouchstart' in window || navigator.msMaxTouchPoints;
}

window.hasClass = function(el, name) {
    if (!el)
        throw new Error('hasClass: invalid element')

    if (el.nodeType !== 1)
        throw new Error('hasClass: expected nodeType is 1, got' + el.nodeType)

    if (window.DOMTokenList && el.classList instanceof DOMTokenList) {
        return el.classList.contains(name)
    } else {
        return (" " + el.className + " ").replace(RE_WHITESPACE, " ").indexOf(" " + name + " ") >= 0
    }
}

window.addClass = function(el, name) {
    if (!hasClass(el, name)) {
        el.className = (el.className ? el.className + ' ' : '') + name;
        return true
    }
    return false
}

window.Cameras = {
    hlsOptions: null,
    hlsHost: null,
    hlsProto: null,
    debugVideoEvents: false,

    setupHls: function(video, name, useHls) {
        var src = this.hlsProto + '://' + this.hlsHost + '/ipcam/' + name + '/live.m3u8';

        // hls.js is not supported on platforms that do not have Media Source Extensions (MSE) enabled.

        // When the browser has built-in HLS support (check using `canPlayType`), we can provide an HLS manifest (i.e. .m3u8 URL) directly to the video element through the `src` property.
        // This is using the built-in support of the plain video element, without using hls.js.

        if (useHls) {
            var config = this.hlsOptions;
            config.xhrSetup = function (xhr,url) {
                xhr.withCredentials = true;
            };

            var hls = new Hls(config);
            hls.loadSource(src);
            hls.attachMedia(video);
            hls.on(Hls.Events.MEDIA_ATTACHED, function () {
                video.muted = true;
                video.play();
            });
        } else {
            console.warn('hls.js is not supported, trying the native way...')

            video.autoplay = true;
            video.muted = true;
            if (window.browserInfo.ios)
                video.setAttribute('controls', 'controls');

            video.src = src;

            var events = ['canplay'];
            if (this.debugVideoEvents)
                events.push('canplay', 'canplaythrough', 'durationchange', 'ended', 'loadeddata', 'loadedmetadata', 'pause', 'play', 'playing', 'progress', 'seeked', 'seeking', 'stalled', 'suspend', 'timeupdate', 'waiting');

            for (var i = 0; i < events.length; i++) {
                var evt = events[i];
                (function(evt, video, name) {
                    video.addEventListener(evt, function(e) {
                        if (this.debugVideoEvents)
                            console.log(name + ': ' + evt, e);

                        if (!window.browserInfo.ios && ['canplay', 'loadedmetadata'].includes(evt))
                            video.play();
                    })
                })(evt, video, name);
            }
        }
    },

    init: function(cams, options, proto, host, debugVideoEvents) {
        // this.cams = cams;
        this.hlsOptions = options;
        this.hlsProto = proto;
        this.hlsHost = host;
        this.debugVideoEvents = debugVideoEvents

        let useHls = Hls.isSupported();
        if (!useHls && !this.hasFallbackSupport()) {
            alert('Neither HLS nor vnd.apple.mpegurl is not supported by your browser.');
            return;
        }

        for (var i = 0; i < cams.length; i++) {
            var name = cams[i];
            var video = document.createElement('video');
            video.setAttribute('id', 'video-'+name);
            document.getElementById('videos').appendChild(video);

            this.setupHls(video, name, useHls);
        }
    },

    hasFallbackSupport: function() {
        var video = document.createElement('video');
        return video.canPlayType('application/vnd.apple.mpegurl');
    },
};
})();