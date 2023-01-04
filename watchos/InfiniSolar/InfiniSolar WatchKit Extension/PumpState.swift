//
//  PumpState.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 09.08.2021.
//

import Alamofire
import SwiftyJSON

public class PumpState: ObservableObject {
    @Published var isEnabled: Bool
    @Published var error: Bool
    @Published var loading: Bool
    @Published var setting: Bool
    
    var request: DataRequest?
    
    init() {
        self.loading = true
        self.error = false
        self.isEnabled = false
        self.request = nil
        self.setting = false
    }
    
    func fetch() {
        self.request = AF.request("http://192.168.5.223:8382/get/").responseJSON { response in
            self.loading = false
            
            switch response.result {
            case .success(let value):
                let json = JSON(value)
                self.isEnabled = json["data"].string == "on"
                
            case .failure(let error):
                switch (error) {
                case .explicitlyCancelled:
                    break
                    
                default:
                    print(error)
                    self.error = true
                }
            }
            
//            self.loading = false
            self.request = nil
        }
    }
    
    func setState(on: Bool) {
        self.setting = true
        self.request = AF.request("http://192.168.5.223:8382/" + (on ? "on" : "off") + "/").responseJSON { response in
            self.setting = false
            
            switch response.result {
            case .success(_):
                self.isEnabled = on
                
            case .failure(let error):
                switch (error) {
                case .explicitlyCancelled:
                    break
                    
                default:
                    print(error)
                    self.error = true
                }
            }
            
            self.request = nil
        }
    }
    
    func abort() {
        if self.request != nil {
            self.request?.cancel()
            self.request = nil
        }
        
        self.error = false
        self.loading = true
        self.isEnabled = false
    }
}
