import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root
    // Compatibilidad con el popover actual; MainShell inyectará esta propiedad.
    property var headerController: null
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        color: root.colors["bg_elevated"]
        border.width: 1
        border.color: root.colors["border"]
    }

    ListView {
        id: suggestions
        anchors.fill: parent
        anchors.margins: Theme.spacingXxs
        clip: true
        spacing: 2
        model: headerController ? headerController.suggestions : []

        delegate: Item {
            id: row
            required property var modelData
            width: suggestions.width
            height: modelData.subtitle.length > 0 ? 54 : 44

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: rowMouse.containsMouse ? root.colors["bg_surface"] : "transparent"
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMd
                anchors.rightMargin: Theme.spacingSm
                spacing: Theme.spacingSm

                Text {
                    text: row.modelData.icon
                    font.family: root.iconFont
                    font.pixelSize: 19
                    color: root.colors["text_secondary"]
                    Layout.alignment: Qt.AlignVCenter
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 0
                    Text {
                        text: row.modelData.title
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: row.modelData.subtitle.length > 0
                        text: row.modelData.subtitle
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeCaption
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
                Item {
                    visible: row.modelData.deletable
                    width: 28
                    height: 28
                    Text {
                        anchors.centerIn: parent
                        text: "\ue5cd"
                        font.family: root.iconFont
                        font.pixelSize: 17
                        color: deleteMouse.containsMouse ? root.colors["text_primary"] : root.colors["text_secondary"]
                    }
                    MouseArea {
                        id: deleteMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (headerController) headerController.removeHistory(row.modelData.title)
                    }
                }
            }
            MouseArea {
                id: rowMouse
                anchors.fill: parent
                anchors.rightMargin: row.modelData.deletable ? 36 : 0
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (headerController) headerController.selectSuggestion(index)
            }
        }

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    }
}
