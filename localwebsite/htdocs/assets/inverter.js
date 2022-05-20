var Inverter = {
    poll: function () {
        setInterval(this._tick, 1000);
    },

    _tick: function() {
        ajax.get('/inverter/status.ajax')
        .then(({response}) => {
            if (response) {
                var el = document.getElementById('inverter_status');
                el.innerHTML = response.html;
            }
        });
    }
};