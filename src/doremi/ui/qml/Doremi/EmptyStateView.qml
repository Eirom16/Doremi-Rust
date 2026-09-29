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

    readonly property var colors: themeBridge.colors

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
            color: root.colors["bg_surface"]

            Text {
                anchors.centerIn: parent
                text: root.icon
                font.family: "Material Symbols Rounded"
                font.pixelSize: 36
                color: root.colors["text_secondary"]
            }
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeTitle
            font.weight: Font.Bold
            color: root.colors["text_primary"]
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.description
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            color: root.colors["text_secondary"]
            wrapMode: Text.WordWrap
            visible: root.description !== ""
        }

        Rectangle {
            id: actionButton
            objectName: "emptyStateAction"
            visible: root.actionText !== ""
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.spacingSm
            implicitWidth: actionLbl.implicitWidth + Theme.spacingLg * 2
            implicitHeight: 36
            radius: Theme.radiusMd
            color: actionMa.containsMouse ? Qt.darker(root.colors["accent"], 1.2) : root.colors["accent"]
            border.width: activeFocus ? 2 : 0
            border.color: root.colors["text_primary"]
            activeFocusOnTab: visible
            Accessible.role: Accessible.Button
            Accessible.name: root.actionText
            Accessible.onPressAction: root.actionClicked()
            Keys.onReturnPressed: function(event) { if (!event.isAutoRepeat) root.actionClicked() }
            Keys.onEnterPressed: function(event) { if (!event.isAutoRepeat) root.actionClicked() }
            Keys.onSpacePressed: function(event) { if (!event.isAutoRepeat) root.actionClicked() }

            Text {
                id: actionLbl
                anchors.centerIn: parent
                text: root.actionText
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                font.weight: Font.Bold
                color: root.colors["text_on_accent"]
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
