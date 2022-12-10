<?php

class InverterHandler extends RequestHandler
{

    public function __construct() {
        parent::__construct();
        $this->tpl->add_static('inverter.js');
    }

    public function GET_status_page() {
        $inv = $this->getClient();

        $status = jsonDecode($inv->exec('get-status'))['data'];
        $rated = jsonDecode($inv->exec('get-rated'))['data'];

        $this->tpl->set([
            'status' => $status,
            'rated' => $rated,
            'html' => $this->renderStatusHtml($status, $rated)
        ]);
        $this->tpl->set_title('Инвертор');
        $this->tpl->render_page('inverter_page.twig');
    }

    public function GET_set_osp() {
        list($osp) = $this->input('e:value(=sub|sbu)');
        $inv = $this->getClient();
        try {
            $inv->exec('set-output-source-priority', [strtoupper($osp)]);
        } catch (Exception $e) {
            die('Ошибка: '.jsonDecode($e->getMessage())['message']);
        }
        redirect('/inverter/');
    }

    public function GET_status_ajax() {
        $inv = $this->getClient();
        $status = jsonDecode($inv->exec('get-status'))['data'];
        $rated = jsonDecode($inv->exec('get-rated'))['data'];
        ajax_ok(['html' => $this->renderStatusHtml($status, $rated)]);
    }

    protected function renderStatusHtml(array $status, array $rated) {
        $power_direction = strtolower($status['battery_power_direction']);
        $power_direction = preg_replace('/ge$/', 'ging', $power_direction);

        $charging_rate = '';
        if ($power_direction == 'charging')
            $charging_rate = sprintf(' @ %s %s',
                $status['battery_charge_current']['value'],
                $status['battery_charge_current']['unit']);
        else if ($power_direction == 'discharging')
            $charging_rate = sprintf(' @ %s %s',
                $status['battery_discharge_current']['value'],
                $status['battery_discharge_current']['unit']);

        $html = sprintf('<b>Battery:</b> %s %s',
            $status['battery_voltage']['value'],
            $status['battery_voltage']['unit']);
        $html .= sprintf(' (%s%s, ',
            $status['battery_capacity']['value'],
            $status['battery_capacity']['unit']);
        $html .= sprintf('%s%s)',
            $power_direction,
            $charging_rate);

        $html .= "\n".sprintf('<b>Load:</b> %s %s',
            $status['ac_output_active_power']['value'],
            $status['ac_output_active_power']['unit']);
        $html .= sprintf(' (%s%%)',
            $status['output_load_percent']['value']);

        if ($status['pv1_input_power']['value'] > 0)
            $html .= "\n".sprintf('<b>Input power:</b> %s %s',
                $status['pv1_input_power']['value'],
                $status['pv1_input_power']['unit']);

        if ($status['grid_voltage']['value'] > 0 or $status['grid_freq']['value'] > 0) {
            $html .= "\n".sprintf('<b>AC input:</b> %s %s',
                $status['grid_voltage']['value'],
                $status['grid_voltage']['unit']);
            $html .= sprintf(', %s %s',
                $status['grid_freq']['value'],
                $status['grid_freq']['unit']);
        }

        $html .= "\n".sprintf('<b>Priority:</b> %s',
            $rated['output_source_priority']);

        return nl2br($html);
    }

    protected function getClient(): InverterdClient {
        global $config;
        $inv = new InverterdClient($config['inverterd_host'], $config['inverterd_port']);
        $inv->setFormat('json');
        return $inv;
    }


}