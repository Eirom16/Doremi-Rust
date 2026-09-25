import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // Compatibilidad con la isla actual; MainShell inyectará esta propiedad.
    property var offlineController: null
    readonly property var colors: themeBridge.colors
    readonly property color warningColor: colors["warning"]
    readonly property string iconFont: "Material Symbols Rounded"

    opacity: offlineController.shown ? 1 : 0
    Behavior on opacity {
        NumberAnimation {
            duration: offlineController.shown ? 350 : 300
            easing.type: offlineController.shown ? Easing.OutCubic : Easing.InCubic
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: Theme.radiusXl
        anchors.rightMargin: Theme.radiusXl
        anchors.topMargin: 4
        anchors.bottomMargin: Theme.spacingXs
        radius: Theme.radiusMd
        color: Qt.rgba(root.warningColor.r, root.warningColor.g, root.warningColor.b, 0.08)
        border.width: 1
        border.color: Qt.rgba(root.warningColor.r, root.warningColor.g, root.warningColor.b, 0.25)

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingMd
            anchors.rightMargin: Theme.spacingMd
            spacing: Theme.spacingSm

            Text {
                text: "\ue648"
                color: root.warningColor
                font.family: root.iconFont
                font.pixelSize: 18
            }

            Label {
                text: "Sin conexion: reproduciendo descargas locales"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                font.weight: Font.Medium
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            Rectangle {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 20
                radius: Theme.radiusSm
                color: Qt.rgba(root.warningColor.r, root.warningColor.g, root.warningColor.b, 0.15)
                border.width: 1
                border.color: Qt.rgba(root.warningColor.r, root.warningColor.g, root.warningColor.b, 0.4)

                Label {
                    anchors.centerIn: parent
                    text: "MODO OFFLINE"
                    color: root.warningColor
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeCaption
                    font.weight: Font.Bold
                }
            }
        }
    }
}
