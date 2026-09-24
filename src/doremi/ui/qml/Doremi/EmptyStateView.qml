import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    property string icon: ""  // Icono musical predeterminado
    property string title: "Sin contenido"
    property string description: "No se encontraron elementos para mostrar."
    property string actionText: ""
    
    signal actionClicked()

    property var colors: (typeof themeBridge !== "undefined" && themeBridge && themeBridge.colors)
                         ? themeBridge.colors
                         : null

    implicitWidth: 320
    implicitHeight: 240

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingMd
        width: Math.min(parent.width - Theme.spacingLg * 2, 400)

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 72
            height: 72
            radius: 36
            color: root.colors ? root.colors["bg_surface"] : "#2a2a3c"

            Text {
                anchors.centerIn: parent
                text: root.icon
                font.family: "Material Symbols Rounded"
                font.pixelSize: 36
                color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
            }
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeTitle
            font.weight: Font.Bold
            color: root.colors ? root.colors["text_primary"] : "#cdd6f4"
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.description
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
            wrapMode: Text.WordWrap
            visible: root.description !== ""
        }

        Rectangle {
            visible: root.actionText !== ""
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.spacingSm
            implicitWidth: actionLbl.implicitWidth + Theme.spacingLg * 2
            implicitHeight: 36
            radius: Theme.radiusMd
            color: actionMa.containsMouse
                   ? (root.colors ? root.colors["accent_bright"] : "#f5c2e7")
                   : (root.colors ? root.colors["accent"] : "#cba6f7")

            Text {
                id: actionLbl
                anchors.centerIn: parent
                text: root.actionText
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                font.weight: Font.Bold
                color: root.colors ? root.colors["bg_base"] : "#11111b"
            }

            MouseArea {
                id: actionMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.actionClicked()
            }
        }
    }
}
