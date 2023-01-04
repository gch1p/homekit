//
//  InverterGenerationState.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 08.08.2021.
//

import Alamofire
import SwiftyJSON

extension Date {
    static var yesterday: Date { return Date().dayBefore }
    static var beforeYesterday: Date { return Date().dayBefore2 }
    var dayBefore: Date {
        return Calendar.current.date(byAdding: .day, value: -1, to: noon)!
    }
    var dayBefore2: Date {
        return Calendar.current.date(byAdding: .day, value: -2, to: noon)!
    }
    var noon: Date {
        return Calendar.current.date(bySettingHour: 12, minute: 0, second: 0, of: self)!
    }
    var month: Int {
        return Calendar.current.component(.month,  from: self)
    }
}

public class InverterGenerationState: ObservableObject {
    @Published var today: Int
    @Published var yesterday: Int
    @Published var dayBeforeYesterday: Int
    @Published var failed: Bool
    
    var request: DataRequest?
    var done: Bool
    
    init() {
        self.request = nil
        self.today = 0
        self.yesterday = 0
        self.dayBeforeYesterday = 0
        self.failed = false
        self.done = false
    }
    
    func fetch() {
        let today = Date()
        let yesterday = Date.yesterday
        let dayBeforeYesterday = Date.beforeYesterday
        
        let cToday = Calendar.current.dateComponents([.day, .month, .year], from: today)
        let cYday1 = Calendar.current.dateComponents([.day, .month, .year], from: yesterday)
        let cYday2 = Calendar.current.dateComponents([.day, .month, .year], from: dayBeforeYesterday)
        
        // shit, this looks like javascript in 2005 :(
        // but it's my second day using swift, please treat me easy lol
        
        // load today
        self.getDayGenerated(arguments: [cToday.year!, cToday.month!, cToday.day!]) { wh in
            self.today = wh
            if cToday.month == cYday1.month {
                // load yesterday
                self.getDayGenerated(arguments: [cYday1.year!, cYday1.month!, cYday1.day!]) { wh in
                    self.yesterday = wh
                    if cToday.month == cYday2.month {
                        // load the day before yesterday
                        self.getDayGenerated(arguments: [cYday2.year!, cYday2.month!, cYday2.day!]) { wh in
                            self.dayBeforeYesterday = wh
                            self.done = true
                        }
                    } else {
                        self.done = true
                    }
                }
            } else {
                self.done = true
            }
        }
    }
    
    func getDayGenerated(arguments: [Int], onComplete: @escaping (Int) -> ()) {
        let args = arguments.map(String.init)
            .joined(separator: ",")
        
        self.request = AF.request("http://192.168.5.223:8380/get-day-generated/?args="+args).responseJSON { response in
            self.request = nil
            
            switch response.result {
            case .success(let value):
                let json = JSON(value)
                onComplete(json["data"]["wh"].int ?? 0)
                
            case .failure(let error):
                switch (error) {
                case .explicitlyCancelled:
                    print("InverterGenerationState: request has been canceled")
                    break
                    
                default:
                    print("InverterGenerationState: oops, something failed")
                    print(error)
                    self.failed = true
                }
            }
        }
    }
    
    func stop() {
        if self.request != nil {
            self.request?.cancel()
            self.request = nil
        }
    }
}
