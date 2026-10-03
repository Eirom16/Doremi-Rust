import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Popup {
    id: root
    objectName: "commandPalette"
    property var controller: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(560, parent ? parent.width - 40 : 560)
    height: Math.min(470, parent ? parent.height - 40 : 470)
    modal: true
    focus: true
    palette.window: themeBridge.colors["bg_elevated"]
    palette.base: themeBridge.colors["bg_surface"]
    palette.text: themeBridge.colors["text_primary"]
    palette.windowText: themeBridge.colors["text_primary"]
    palette.placeholderText: themeBridge.colors["text_secondary"]
    palette.button: themeBridge.colors["bg_surface"]
    palette.buttonText: themeBridge.colors["text_primary"]
    palette.highlight: themeBridge.colors["accent"]
    palette.highlightedText: themeBridge.colors["text_on_accent"]
    padding: 16
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: { query.clear(); controller.search(""); query.forceActiveFocus() }
    background: Rectangle { color: themeBridge.colors["bg_elevated"]; radius: Theme.radiusLg; border.color: themeBridge.colors["border"] }
    function invoke() {
        if (choices.currentIndex >= 0 && choices.currentIndex < controller.results.length) {
            var key = controller.results[choices.currentIndex].id
            close()
            controller.execute(key)
        }
    }
    contentItem: ColumnLayout {
        TextField {
            id: query
            objectName: "commandQuery"
            Layout.fillWidth: true
            placeholderText: "Buscar canción o comando…"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            Accessible.name: "Buscar comandos"
            onTextChanged: { if (root.controller) root.controller.search(text); choices.currentIndex = 0 }
            Keys.onDownPressed: choices.currentIndex = Math.min(choices.count - 1, choices.currentIndex + 1)
            Keys.onUpPressed: choices.currentIndex = Math.max(0, choices.currentIndex - 1)
            Keys.onReturnPressed: root.invoke()
            Keys.onEnterPressed: root.invoke()
        }
        ListView {
            id: choices
            objectName: "commandResults"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.controller ? root.controller.results : []
            currentIndex: 0
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                width: choices.width
                text: modelData.title
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
                highlighted: choices.currentIndex === index
                onClicked: { choices.currentIndex = index; root.invoke() }
            }
        }
    }
}
