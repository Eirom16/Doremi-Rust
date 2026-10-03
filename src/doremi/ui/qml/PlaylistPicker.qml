import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Popup {
    id: root
    property var controller: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(440, parent ? parent.width - 32 : 440)
    height: 440
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
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: themeBridge.colors["bg_elevated"]; radius: Theme.radiusLg; border.color: themeBridge.colors["border"] }
    Connections {
        target: root.controller
        function onOpened() { root.open() }
        function onClosed() { root.close() }
    }
    contentItem: ColumnLayout {
        Label { text: "Añadir a playlist"; font.pixelSize: Theme.typeHeading; color: themeBridge.colors["text_primary"] }
        Label { text: root.controller ? root.controller.errorText : ""; visible: text !== ""; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: themeBridge.colors["error"] }
        BusyIndicator { running: root.controller ? root.controller.busy : false; visible: running }
        TextField { id: filter; Layout.fillWidth: true; placeholderText: "Buscar playlist"; Accessible.name: "Buscar playlist" }
        ListView {
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: root.controller ? root.controller.playlists : []
            delegate: ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: modelData.title + " · " + (modelData.subtitle || "Local")
                visible: modelData.title.toLowerCase().indexOf(filter.text.toLowerCase()) >= 0
                height: visible ? implicitHeight : 0
                enabled: root.controller && !root.controller.busy
                onClicked: root.controller.choose(modelData.id)
            }
        }
        RowLayout {
            TextField { id: title; Layout.fillWidth: true; placeholderText: "Nueva playlist local"; Accessible.name: "Nombre de playlist local" }
            Button { text: "Crear"; enabled: root.controller && !root.controller.busy && title.text.trim() !== ""; onClicked: root.controller.create(title.text) }
        }
    }
}
