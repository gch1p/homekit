//
//  InverterStatus.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 03.08.2021.
//

import Foundation

struct InverterStatus: Hashable {
    public var batteryVoltage: Float
    public var batteryCapacity: Int
    public var activePower: Int
    public var pvInputPower: Int
    
    init(batteryVoltage: Float, batteryCapacity: Int, activePower: Int, pvInputPower: Int) {
        self.batteryVoltage = batteryVoltage
        self.batteryCapacity = batteryCapacity
        self.activePower = activePower
        self.pvInputPower = pvInputPower
    }
    
    func hasData() -> Bool {
        return self.batteryVoltage != 0
            || self.batteryCapacity != 0
            || self.activePower != 0
            || self.pvInputPower != 0
    }
}
