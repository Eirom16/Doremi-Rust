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

    readonly property var colors: themeBridge.colors

    Accessible.role: Accessible.Button
    Accessible.name: root.title + (root.subtitle !== "" ? ", " + root.subtitle : "")
    Accessible.onPressAction: root.clicked()
    activeFocusOnTab: true
    Keys.onReturnPressed: if (!event.isAutoRepeat) root.clicked()
    Keys.onEnterPressed: if (!event.isAutoRepeat) root.clicked()
    Keys.onSpacePressed: if (!event.isAutoRepeat) root.clicked()

    radius: Theme.radiusLg
    color: ma.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
    border.width: 1
    border.color: ma.containsMouse ? root.colors["border_focus"] : root.colors["border"]

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
            color: root.colors["bg_elevated"]
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
                color: root.colors["bg_elevated"]

                Text {
                    anchors.centerIn: parent
                    text: root.isArtist ? "" : ""
                    font.family: "Material Symbols Rounded"
                    font.pixelSize: 36
                    color: root.colors["text_disabled"]
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
                color: root.colors["accent"]
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
                    color: root.colors["bg_base"]
                }

                MouseArea {
                    id: playMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.playClicked()
                }
                Accessible.role: Accessible.Button
                Accessible.name: "Reproducir " + root.title
                Accessible.onPressAction: root.playClicked()
                activeFocusOnTab: true
                Keys.onReturnPressed: if (!event.isAutoRepeat) root.playClicked()
                Keys.onEnterPressed: if (!event.isAutoRepeat) root.playClicked()
                Keys.onSpacePressed: if (!event.isAutoRepeat) root.playClicked()
            }

            // Download badge
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: Theme.spacingXs
                width: 20
                height: 20
                radius: 10
                color: root.colors["bg_base"]
                visible: root.isDownloaded

                Text {
                    anchors.centerIn: parent
                    text: ""
                    font.family: "Material Symbols Rounded"
                    font.pixelSize: 13
                    color: root.colors["accent"]
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeBody
            font.weight: Font.Medium
            color: root.colors["text_primary"]
            elide: Text.ElideRight
            horizontalAlignment: root.isArtist ? Text.AlignHCenter : Text.AlignLeft
        }

        Text {
            Layout.fillWidth: true
            text: root.subtitle
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeCaption
            color: root.colors["text_secondary"]
            elide: Text.ElideRight
            visible: root.subtitle !== ""
            horizontalAlignment: root.isArtist ? Text.AlignHCenter : Text.AlignLeft
        }
    }


}
