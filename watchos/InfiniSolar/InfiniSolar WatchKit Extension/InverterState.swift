//
//  InverterStatusFetcher.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 03.08.2021.
//

import Alamofire
import SwiftyJSON

public class InverterState: ObservableObject {
    @Published var status: InverterStatus
    @Published var fetchError: Bool = false
    
    var timer: Timer?
    var request: DataRequest?
    
    func startFetching() {
        if self.timer != nil {
            self.stopFetching()
        }
        
        self.timer = Timer.scheduledTimer(timeInterval: 1,
                                          target: self,
                                          selector: #selector(fetchStatus),
                                          userInfo: nil,
                                          repeats: true)
//        self.timer?.fire()
    }
    
    func stopFetching() {
        if self.request != nil {
            self.request?.cancel()
            self.request = nil
        }
        
        self.fetchError = false
        self.timer?.invalidate()
        self.timer = nil
    }
    
    @objc func fetchStatus() {
        self.fetchError = false
        
        self.request = AF.request("http://192.168.5.223:8380/get-status/").responseJSON {
            response in
            switch response.result {
                case .success(let value):
                    let json = JSON(value)
                    self.status.activePower = json["data"]["ac_output_active_power"]["value"].int ?? 0
                    self.status.batteryVoltage = json["data"]["battery_voltage"]["value"].float ?? 0
                    self.status.batteryCapacity = json["data"]["battery_capacity"]["value"].int ?? 0
                    self.status.pvInputPower = json["data"]["pv1_input_power"]["value"].int ?? 0
            
                case .failure(let error):
                    switch (error) {
                    case .explicitlyCancelled:
                        print("InverterStatusFetcher: request has been canceled")
                        break
                        
                    default:
                        self.fetchError = true
                        self.timer?.invalidate()
                        self.timer = nil
                    }
            }
            
            self.request = nil
        }
    }
    
    init() {
        self.fetchError = false
        self.status = InverterStatus(batteryVoltage: 0, batteryCapacity: 0, activePower: 0, pvInputPower: 0)
        self.timer = nil
        self.request = nil
    }
}
