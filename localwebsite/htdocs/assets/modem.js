var ModemStatus = {
    _modems: [],

    init: function(modems) {
        for (var i = 0; i < modems.length; i++) {
            var modem = modems[i];
            this._modems.push(new ModemStatusUpdater(modem));
        }
    }
};


function ModemStatusUpdater(id) {
    this.id = id;
    this.elem = ge('modem_data_'+id);
    this.fetch();
}
extend(ModemStatusUpdater.prototype, {
    fetch: function() {
        ajax.get('/modem/status/get.ajax', {
            id: this.id
        }).then(({response}) => {
            var {html} = response;
            this.elem.innerHTML = html;

            // TODO enqueue rerender
        });
    },
});