//
//  MainPumpView.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 09.08.2021.
//

import SwiftUI

struct PumpView: View {
    @ObservedObject var state = PumpState()
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Water pump")
                .font(.title2)
                .fontWeight(.thin)
            Spacer().frame(height: 10)
            
            if self.state.loading == true {
                Text("Loading...")
                    .fontWeight(.thin)
            }
            
            else if self.state.error == true {
                Text("Connection error.")
            }
            
            else {
                if self.state.isEnabled == true {
                    Text("The pump is ").fontWeight(.thin)
                        + Text("turned on")
                    Spacer().frame(height: 10)
                    Button(self.state.setting ? "..." : "Turn off") {
                        self.state.setState(on: false)
                    }
                } else {
                    Text("The pump is ").fontWeight(.thin)
                        + Text("turned off")
                    Spacer().frame(height: 10)
                    Button(self.state.setting ? "..." : "Turn on") {
                        self.state.setState(on: true)
                    }
                }
            }
        }
        .onAppear() {
            self.state.fetch()
        }
        .onDisappear() {
            self.state.abort()
        }
    }
}

struct PumpView_Previews: PreviewProvider {
    static var previews: some View {
        PumpView()
    }
}
