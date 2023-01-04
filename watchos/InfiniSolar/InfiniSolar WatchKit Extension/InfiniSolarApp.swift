//
//  InfiniSolarApp.swift
//  InfiniSolar WatchKit Extension
//
//  Created by Evgeny Zinoviev on 03.08.2021.
//

import SwiftUI

@main
struct InfiniSolarApp: App {
    @SceneBuilder var body: some Scene {
        WindowGroup {
            NavigationView {
                ScrollView(.vertical) {
                    VStack(alignment: .leading) {
                        InverterView()
                        self.divider()
                        
                        RoomView()
                        self.divider()
                        
                        PumpView()
                    }
                    .frame(
                        minWidth: 0,
                        maxWidth: .infinity,
                        minHeight: 0,
                        maxHeight: .infinity,
                        alignment: .topLeading
                    )
                }
            }
        }

        WKNotificationScene(controller: NotificationController.self, category: "myCategory")
    }
    
    func divider() -> some View {
        return Divider()
            .padding(EdgeInsets(top: 12, leading: 4, bottom: 12, trailing: 4))
    }
}
