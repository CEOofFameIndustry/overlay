import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
ShellRoot {
    id: root
    property string target: Quickshell.env("MEET_VOICE_SCREEN") || ""
    property string bodyText: Quickshell.env("MEET_VOICE_TEXT") || ""
    property int duration: Number(Quickshell.env("MEET_VOICE_MS") || "90000")
    IpcHandler {
        target: "meetvoice"
        function hide(): void { Qt.quit() }
        function show(message: string, screenName: string, milliseconds: int): void {
            root.bodyText = message; root.target = screenName
            timer.interval = milliseconds; timer.restart()
        }
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            visible: modelData.name === root.target && root.bodyText.length > 0
            implicitWidth: Math.min(720, modelData.width * 0.8)
            implicitHeight: Math.min(modelData.height * 0.48, Math.max(80, measure.implicitHeight + 66))
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "meet-voice-private"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            Text {
                id: measure
                visible: false
                width: panel.width - 36
                text: root.bodyText
                wrapMode: Text.Wrap
                font.pixelSize: 14
                textFormat: Text.PlainText
            }
            Rectangle {
                anchors.fill: parent
                color: "#f025292f"
                radius: 10
                border.color: "#7c8795"
                Text { text: "Meet Voice"; color: "#acb9c8"; font.pixelSize: 11; x: 16; y: 10 }
                Button { text: "×"; width: 28; height: 24; anchors { right: parent.right; top: parent.top; margins: 6 } onClicked: Qt.quit() }
                ScrollView {
                    anchors { fill: parent; topMargin: 38; leftMargin: 16; rightMargin: 16; bottomMargin: 14 }
                    clip: true
                    TextArea {
                        text: root.bodyText
                        textFormat: TextEdit.PlainText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: "#f3f5f7"
                        font.pixelSize: 14
                        background: null
                    }
                }
            }
        }
    }
    Timer { id: timer; interval: root.duration; running: true; onTriggered: Qt.quit() }
}
