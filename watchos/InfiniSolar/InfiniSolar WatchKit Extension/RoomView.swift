//
//  MainRoomView.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 08.08.2021.
//

import SwiftUI

struct RoomView: View {
    @ObservedObject var state = RoomState()
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Room")
                .font(.title2)
                .fontWeight(.thin)
            Spacer().frame(height: 10)
            
            if self.state.error {
                Text("Failed to fetch data from si7021d.")
            }
            
            else {
                Text("Temperature is ").fontWeight(.thin) + Text(String(self.state.temp) + " °C")
                Text("Rel. humidity is ").fontWeight(.thin) + Text(String(self.state.rh) + " %")
            }
        }
        .onAppear() {
            self.state.start()
        }
        .onDisappear() {
            self.state.stop()
        }
    }
}

struct RoomView_Previews: PreviewProvider {
    static var previews: some View {
        RoomView()
    }
}
