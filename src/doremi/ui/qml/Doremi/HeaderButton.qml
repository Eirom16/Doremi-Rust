// Botón de cabecera estilo pill, usado por las islas QML (Downloads, etc.).
// Variantes: normal | activo (acento) | danger (error).
import QtQuick
import QtQuick.Controls
import Doremi 1.0

Rectangle {
    id: btn

    signal clicked()

    property string text: ""
    property bool active: false
    property bool danger: false

    readonly property color accentColor: themeBridge.colors["accent"]

    width: lbl.implicitWidth + Theme.spacingLg * 1.5
    height: 34
    radius: Theme.radiusPill
    color: {
        if (danger)
            return ma.containsMouse ? Qt.rgba(244, 63, 94, 0.2) : Qt.rgba(244, 63, 94, 0.1)
        if (active)
            return Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.15)
        return ma.containsMouse ? themeBridge.colors["bg_elevated"] : themeBridge.colors["bg_surface"]
    }
    border.width: 1
    border.color: {
        if (danger)
            return Qt.rgba(244, 63, 94, 0.3)
        if (active)
            return Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.3)
        return themeBridge.colors["border"]
    }

    Label {
        id: lbl
        anchors.centerIn: parent
        text: btn.text
        color: btn.danger ? themeBridge.colors["error"]
             : (btn.active ? btn.accentColor : themeBridge.colors["text_primary"])
        font.family: Theme.fontFamily
        font.pixelSize: Theme.typeLabel
        font.weight: Font.DemiBold
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}
