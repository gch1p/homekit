//
//  RoomState.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 09.08.2021.
//

import Alamofire
import SwiftyJSON

extension Double {
    /// Rounds the double to decimal places value
    func rounded(toPlaces places:Int) -> Double {
        let divisor = pow(10.0, Double(places))
        return (self * divisor).rounded() / divisor
    }
}


public class RoomState: ObservableObject {
    @Published var temp: Double
    @Published var rh: Double
    @Published var error: Bool
    
    var timer: Timer?
    var request: DataRequest?
    
    init() {
        self.error = false
        self.timer = nil
        self.request = nil
        
        self.temp = 0
        self.rh = 0
    }
    
    func start() {
        if self.timer != nil {
            self.stop()
        }
        
        self.timer = Timer.scheduledTimer(timeInterval: 5,
                                          target: self,
                                          selector: #selector(fetch),
                                          userInfo: nil,
                                          repeats: true)
        self.timer?.fire()
    }
    
    func stop() {
        if self.request != nil {
            self.request?.cancel()
            self.request = nil
        }
        
        self.error = false
        self.timer?.invalidate()
        self.timer = nil
    }
    
    @objc func fetch() {
        self.request = AF.request("http://192.168.5.223:8381/read/").responseJSON { response in
            self.request = nil
            
            switch response.result {
            case .success(let value):
                let j = JSON(value)
                self.temp = (j["temp"].double ?? 0).rounded(toPlaces: 2)
                self.rh = (j["humidity"].double ?? 0).rounded(toPlaces: 2)
                
            case .failure(let error):
                switch (error) {
                case .explicitlyCancelled:
                    break
                    
                default:
                    self.error = true
                    self.timer?.invalidate()
                    self.timer = nil
                }
            }
        }
    }
}
