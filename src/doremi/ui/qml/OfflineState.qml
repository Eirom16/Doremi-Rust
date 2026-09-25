import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root
    property var screenVm: null
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(420, Math.max(280, parent.width - Theme.spacingXxl * 2))
        spacing: Theme.spacingMd

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 72
            height: 72
            radius: width / 2
            color: root.colors["bg_surface"]

            Text {
                anchors.centerIn: parent
                text: "\ue648"
                font.family: root.iconFont
                font.pixelSize: 34
                color: root.colors["warning"]
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Sin conexión"
            horizontalAlignment: Text.AlignHCenter
            color: root.colors["text_primary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeTitle
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            text: screenVm.message
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            color: root.colors["text_secondary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
        }

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.spacingSm
            width: actionLabel.implicitWidth + Theme.spacingLg * 2
            height: 38
            radius: Theme.radiusMd
            color: actionMouse.containsMouse ? root.colors["accent_bright"] : root.colors["accent"]

            Text {
                id: actionLabel
                anchors.centerIn: parent
                text: screenVm.actionText
                color: root.colors["text_on_accent"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                font.weight: Font.DemiBold
            }
            MouseArea {
                id: actionMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: screenVm.retry()
            }
        }
    }
}
