var ajax = {
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

function extend(a, b) {
    return Object.assign(a, b);
}

function ge(id) {
    return document.getElementById(id);
}

(function() {
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
})();
