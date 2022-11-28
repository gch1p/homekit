function isObject(o) {
    return Object.prototype.toString.call(o) === '[object Object]';
}

function ge(id) {
    return document.getElementById(id)
}

function cancelEvent(evt) {
    if (evt.preventDefault) evt.preventDefault();
    if (evt.stopPropagation) evt.stopPropagation();

    evt.cancelBubble = true;
    evt.returnValue = false;

    return false;
}

function errorText(e) {
    return e instanceof Error ? e.message : e+''
}

(function() {
    function request(method, url, data, callback) {
        data = data || null;

        if (typeof callback != 'function') {
            throw new Error('callback must be a function');
        }

        if (!url)
            throw new Error('no url specified');

        switch (method) {
            case 'GET':
                if (isObject(data)) {
                    for (var k in data) {
                        if (data.hasOwnProperty(k))
                            url += (url.indexOf('?') === -1 ? '?' : '&')+encodeURIComponent(k)+'='+encodeURIComponent(data[k])
                    }
                }
                break;

            case 'POST':
                if (isObject(data)) {
                    var sdata = [];
                    for (var k in data) {
                        if (data.hasOwnProperty(k))
                            sdata.push(encodeURIComponent(k)+'='+encodeURIComponent(data[k]));
                    }
                    data = sdata.join('&');
                }
                break;
        }

        var xhr = new XMLHttpRequest();
        xhr.open(method, url);

        if (method === 'POST')
            xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if ('status' in xhr && !/^2|1223/.test(xhr.status))
                    throw new Error('http code '+xhr.status)
                callback(null, JSON.parse(xhr.responseText));
            }
        };
        xhr.onerror = function(e) {
            callback(e, null);
        };

        xhr.send(method === 'GET' ? null : data);
        return xhr;
    }

    window.ajax = {
        get: request.bind(request, 'GET'),
        post: request.bind(request, 'POST')
    }
})();


function lock(el) {
    el.setAttribute('disabled', 'disabled');
}

function unlock(el) {
    el.removeAttribute('disabled');
}

function initNetworkSettings() {
    function setupField(el, value) {
        if (value !== null)
            el.value = value;
        unlock(el);
    }

    var doneRequestsCount = 0;
    function onRequestDone() {
        doneRequestsCount++;
        if (doneRequestsCount === 2) {
            ge('loading_label').style.display = 'none';
        }
    }

    var form = document.forms.network_settings;
    form.addEventListener('submit', function(e) {
        if (!form.nid.value.trim()) {
            alert('Введите node id');
            return cancelEvent(e);
        }

        if (form.psk.value.length < 8) {
            alert('Неверный пароль (минимальная длина - 8 символов)');
            return cancelEvent(e);
        }

        if (form.ssid.selectedIndex == -1) {
            alert('Не выбрана точка доступа');
            return cancelEvent(e);
        }

        lock(form.submit)
    })
    form.show_psk.addEventListener('change', function(e) {
        form.psk.setAttribute('type', e.target.checked ? 'text' : 'password');
    });
    form.ssid.addEventListener('change', function(e) {
        var i = e.target.selectedIndex;
        if (i !== -1) {
            var opt = e.target.options[i];
            if (opt)
                form.psk.value = '';
        }
    });

    ajax.get('/status', {}, function(error, response) {
        try {
            if (error)
                throw error;

            setupField(form.nid, response.node_id || null);
            setupField(form.psk, null);
            setupField(form.submit, null);

            onRequestDone();
        } catch (error) {
            alert(errorText(error));
        }
    });

    ajax.get('/scan', {}, function(error, response) {
        try {
            if (error)
                throw error;

            form.ssid.innerHTML = '';
            for (var i = 0; i < response.list.length; i++) {
                var ssid = response.list[i][0];
                var rssi = response.list[i][1];
                form.ssid.append(new Option(ssid + ' (' + rssi + ' dBm)', ssid));
            }
            unlock(form.ssid);

            onRequestDone();
        } catch (error) {
            alert(errorText(error));
        }
    });
}

function initUpdateForm() {
    var form = document.forms.update_settings;
    form.addEventListener('submit', function(e) {
        cancelEvent(e);
        if (!form.file.files.length) {
            alert('Файл обновления не выбран');
            return false;
        }

        lock(form.submit);

        var xhr = new XMLHttpRequest();
        var fd = new FormData();
        fd.append('file', form.file.files[0]);

        xhr.upload.addEventListener('progress', function (e) {
            var total = form.file.files[0].size;
            var progress;
            if (e.loaded < total) {
                progress = Math.round(e.loaded / total * 100).toFixed(2);
            } else {
                progress = 100;
            }
            form.submit.innerHTML = progress + '%';
        });
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                var response = JSON.parse(xhr.responseText);
                if (response.result === 1) {
                    alert('Обновление завершено, устройство перезагружается');
                } else {
                    alert('Ошибка обновления');
                }
            }
        };
        xhr.onerror = function(e) {
            alert(errorText(e))
        };

        xhr.open('POST', e.target.action);
        xhr.send(fd);

        return false;
    });
}

function initApp() {
    initNetworkSettings();
    initUpdateForm();
}