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