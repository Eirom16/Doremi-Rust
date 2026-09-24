import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Rectangle {
    id: root

    property int itemIndex: 0
    property string title: ""
    property string artist: ""
    property string duration: ""
    property string thumbnail: ""
    property bool isPlaying: false
    property bool isLiked: false
    property bool isDownloaded: false

    signal playRequested()
    signal likeRequested()
    signal menuRequested()

    property var colors: (typeof themeBridge !== "undefined" && themeBridge && themeBridge.colors)
                         ? themeBridge.colors
                         : null

    implicitHeight: 48
    radius: Theme.radiusMd
    color: root.isPlaying
           ? (root.colors ? root.colors["bg_high"] : "#313244")
           : (ma.containsMouse
              ? (root.colors ? root.colors["bg_surface"] : "#1e1e2e")
              : "transparent")

    Behavior on color { ColorAnimation { duration: 100 } }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onDoubleClicked: root.playRequested()
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingSm
        anchors.rightMargin: Theme.spacingSm
        spacing: Theme.spacingMd

        // Index / Play Icon
        Item {
            width: 24
            height: 24

            Text {
                anchors.centerIn: parent
                text: root.isPlaying ? "" : (ma.containsMouse ? "" : (root.itemIndex + 1).toString())
                font.family: (root.isPlaying || ma.containsMouse) ? "Material Symbols Rounded" : Theme.fontMono
                font.pixelSize: (root.isPlaying || ma.containsMouse) ? 18 : Theme.typeCaption
                color: root.isPlaying
                       ? (root.colors ? root.colors["accent"] : "#cba6f7")
                       : (root.colors ? root.colors["text_secondary"] : "#a6adc8")
            }
        }

        // Thumbnail (Optional)
        Rectangle {
            visible: root.thumbnail !== ""
            width: 32
            height: 32
            radius: Theme.radiusSm
            color: root.colors ? root.colors["bg_elevated"] : "#181825"
            clip: true

            Image {
                anchors.fill: parent
                source: root.thumbnail
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
        }

        // Title & Artist
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                Layout.fillWidth: true
                text: root.title
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
                font.weight: root.isPlaying ? Font.Bold : Font.Normal
                color: root.isPlaying
                       ? (root.colors ? root.colors["accent"] : "#cba6f7")
                       : (root.colors ? root.colors["text_primary"] : "#cdd6f4")
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: root.artist
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeCaption
                color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
                elide: Text.ElideRight
                visible: root.artist !== ""
            }
        }

        // Download Badge
        Text {
            visible: root.isDownloaded
            text: ""
            font.family: "Material Symbols Rounded"
            font.pixelSize: 16
            color: root.colors ? root.colors["accent"] : "#cba6f7"
        }

        // Like Button
        Rectangle {
            width: 28
            height: 28
            radius: 14
            color: likeMa.containsMouse
                   ? (root.colors ? root.colors["bg_high"] : "#45475a")
                   : "transparent"

            Text {
                anchors.centerIn: parent
                text: root.isLiked ? "" : ""
                font.family: "Material Symbols Rounded"
                font.pixelSize: 18
                color: root.isLiked
                       ? (root.colors ? root.colors["accent"] : "#cba6f7")
                       : (root.colors ? root.colors["text_disabled"] : "#6c7086")
            }

            MouseArea {
                id: likeMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.likeRequested()
            }
        }

        // Duration
        Text {
            text: root.duration
            font.family: Theme.fontMono
            font.pixelSize: Theme.typeCaption
            color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
            visible: root.duration !== ""
        }

        // Menu Button
        Rectangle {
            width: 28
            height: 28
            radius: 14
            color: menuMa.containsMouse
                   ? (root.colors ? root.colors["bg_high"] : "#45475a")
                   : "transparent"

            Text {
                anchors.centerIn: parent
                text: ""
                font.family: "Material Symbols Rounded"
                font.pixelSize: 18
                color: root.colors ? root.colors["text_secondary"] : "#a6adc8"
            }

            MouseArea {
                id: menuMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.menuRequested()
            }
        }
    }


}
