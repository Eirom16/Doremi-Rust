// Botón hero de pantallas de detalle (Álbum/Playlist): pill grande.
// primary=true → relleno de acento; si no, fondo secundario con borde.
import QtQuick
import QtQuick.Controls
import Doremi 1.0

Rectangle {
    id: btn

    signal clicked()
    activeFocusOnTab: enabled && visible
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (enabled) clicked()
    Keys.onReturnPressed: if (enabled && !event.isAutoRepeat) clicked()
    Keys.onEnterPressed: if (enabled && !event.isAutoRepeat) clicked()
    Keys.onSpacePressed: if (enabled && !event.isAutoRepeat) clicked()

    property bool primary: false
    property string text: ""
    property string iconCode: ""

    readonly property var colors: themeBridge.colors
    readonly property color accentColor: colors["accent"]

    implicitWidth: row.implicitWidth + Theme.spacingLg * 2
    implicitHeight: 44
    radius: Theme.radiusPill
    color: {
        if (!enabled) return colors["bg_high"]
        if (primary) return ma.containsMouse ? colors["accent_bright"] : accentColor
        return ma.containsMouse ? colors["bg_high"] : colors["bg_elevated"]
    }
    border.width: activeFocus ? 2 : (primary ? 0 : 1)
    border.color: activeFocus || ma.containsMouse ? accentColor : colors["border"]

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spacingXs

        Text {
            visible: btn.iconCode !== ""
            text: btn.iconCode
            font.family: "Material Symbols Rounded"
            font.pixelSize: 18
            color: btn.primary ? btn.colors["text_on_accent"] : btn.colors["text_primary"]
            anchors.verticalCenter: parent.verticalCenter
        }
        Label {
            text: btn.text
            color: btn.primary ? btn.colors["text_on_accent"] : btn.colors["text_primary"]
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.weight: Font.Bold
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        enabled: btn.enabled
        cursorShape: btn.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: { btn.forceActiveFocus(); btn.clicked() }
    }
}
