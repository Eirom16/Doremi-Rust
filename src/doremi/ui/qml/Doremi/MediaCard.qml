import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property string thumbnail: ""
    property bool isDownloaded: false
    property bool isArtist: false
    readonly property bool hovered: ma.containsMouse || playMa.containsMouse

    signal clicked()
    signal playClicked()
    signal menuClicked()

    property var colors: (typeof themeBridge !== "undefined" && themeBridge && themeBridge.colors)
                         ? themeBridge.colors
                         : null

    radius: Theme.radiusLg
    color: ma.containsMouse
           ? (root.colors ? root.colors["bg_high"] : "#313244")
           : (root.colors ? root.colors["bg_surface"] : "#1e1e2e")
    border.width: 1
    border.color: ma.containsMouse
                  ? (root.colors ? root.colors["border_focus"] : "#585b70")
                  : (root.colors ? root.colors["border"] : "#313244")

    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingSm
        spacing: Theme.spacingXs

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.isArtist ? height / 2 : Theme.radiusMd
            color: root.colors ? root.colors["bg_elevated"] : "#181825"
            clip: true

            Image {
                anchors.fill: parent
                source: root.thumbnail
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: status === Image.Ready
            }

            Rectangle {
                anchors.fill: parent
                visible: root.thumbnail === ""
                color: root.colors ? root.colors["bg_elevated"] : "#181825"

                Text {
                    anchors.centerIn: parent
                    text: root.isArtist ? "" : ""
                    font.family: "Material Symbols Rounded"
                    font.pixelSize: 36
                    color: root.colors ? root.colors["text_disabled"] : "#6c7086"
                }
            }

            // Play button overlay on hover
            Rectangle {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Theme.spacingSm
                width: 38
                height: 38
                radius: 19
                color: root.colors ? root.colors["accent"] : "#cba6f7"
                opacity: root.hovered ? 1.0 : 0.0
                scale: root.hovered ? 1.0 : 0.8
                visible: !root.isArtist

                Behavior on opacity { NumberAnimation { duration: 150 } }
                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }

                Text {
                    anchors.centerIn: parent
                    text: ""
                    font.family: "Material Symbols Rounded"
                    font.pixelSize: 22
                    color: root.colors ? root.colors["bg_base"] : "#11111b"
                }

                MouseArea {
                    id: playMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.playClicked()
                }
            }

            // Download badge
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: Theme.spacingXs
                width: 20
                height: 20
                radius: 10
                color: root.colors ? root.colors["bg_base"] : "#11111b"
                visible: root.isDownloaded

                Text {
                    anchors.centerIn: parent
                    text: ""
                    font.family: "Material Symbols Rounded"
                    font.pixelSize: 13
                    color: root.colors ? root.colors["accent"] : "#cba6f7"
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            font.weight: Font.Medium
            color: root.colors ? root.colors["text_primary"] : "#cdd6f4"
            elide: Text.ElideRight
            horizontalAlignment: root.isArtist ? Text.AlignHCenter : Text.AlignLeft
        }

        Text {
            Layout.fillWidth: true
            text: root.subtitle
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeCaption
            color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
            elide: Text.ElideRight
            visible: root.subtitle !== ""
            horizontalAlignment: root.isArtist ? Text.AlignHCenter : Text.AlignLeft
        }
    }


}
