//
//  MainInverterView.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 08.08.2021.
//

import SwiftUI

struct InverterView: View {
    @ObservedObject var state = InverterState()
    @State var isPresented = false
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Inverter")
                .font(.title2)
                .fontWeight(.thin)
            Spacer().frame(height: 10)
            
            // inverter data
            if self.state.fetchError == true {
                Text("Error while fetching status.")
                    .multilineTextAlignment(.leading)
                
                Spacer().frame(height: 10)
                
                Button(action:{
                    self.state.startFetching()
                }) {
                    Text("Retry")
                }
    //            } else if !self.state.status.hasData() {
    //                ProgressView()
    //                    .progressViewStyle(CircularProgressViewStyle())
            } else {
                Group {
                    Text(String(self.state.status.batteryVoltage) + " V")
                        + Text(" ≈ " + String(self.state.status.batteryCapacity) + " %").fontWeight(.thin)
                    
                    Spacer().frame(height: 1)
                    
                    Text("Active load is ").fontWeight(.thin)
                        + Text(String(self.state.status.activePower) + " Wh")
                    
                    if self.state.status.pvInputPower > 0 {
                        Divider()
                        
                        Text("Consuming ").fontWeight(.thin)
                            + Text(String(self.state.status.pvInputPower) + " Wh")
                            + Text(" from panels").fontWeight(.thin)
                    }
                    
                    Spacer().frame(height: 15)
                    NavigationLink(destination: GenerationView(), isActive: $isPresented) {
                        Text("Generation stats")
                            .onTapGesture{
                                self.isPresented = true
                                self.state.stopFetching()
                            }
                    }
                }
            }
        }
        .onAppear() {
            self.state.startFetching()
        }
    }
}

struct InverterView_Previews: PreviewProvider {
    static var previews: some View {
        InverterView()
    }
}
