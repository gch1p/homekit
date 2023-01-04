//
//  GenerationView.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 08.08.2021.
//

import SwiftUI

struct GenerationView: View {
    @ObservedObject var state = InverterGenerationState()
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Generation")
                .font(.title2)
                .fontWeight(.thin)
            Spacer().frame(height: 10)
            
            if self.state.failed == true {
                Text("Error while fetching info.")
                    .multilineTextAlignment(.leading)
                
                Spacer().frame(height: 10)
                
                Button(action:{
                    self.state.fetch()
                }) {
                    Text("Retry")
                }
            } else if !self.state.done {
                ProgressView().progressViewStyle(CircularProgressViewStyle())
            } else {
                Text("Today: ")
                    + Text(String(self.state.today) + " Wh").fontWeight(.thin)
                
                if self.state.yesterday > 0 {
                    Spacer().frame(height: 5)
                    Text("Yesterday: ")
                        + Text(String(self.state.yesterday) + " Wh").fontWeight(.thin)
                }
                
                if self.state.dayBeforeYesterday > 0 {
                    Spacer().frame(height: 5)
                    Text("The day before yesterday: ")
                        + Text(String(self.state.dayBeforeYesterday) + " Wh").fontWeight(.thin)
                }
            }
        }.frame(
            minWidth: 0,
            maxWidth: .infinity,
            minHeight: 0,
            maxHeight: .infinity,
            alignment: .topLeading
        ).onAppear() {
            self.state.fetch()
        }.onDisappear() {
            self.state.stop()
        }
    }
}

struct GenerationView_Previews: PreviewProvider {
    static var previews: some View {
        GenerationView()
    }
}
