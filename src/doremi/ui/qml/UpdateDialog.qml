import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property bool dialogAvailable: typeof updateDialog !== "undefined" && updateDialog
    readonly property string dialogVersion: dialogAvailable ? updateDialog.version : ""
    readonly property string dialogCurrentVersion: dialogAvailable ? updateDialog.currentVersion : ""
    readonly property string dialogReleaseNotes: dialogAvailable ? updateDialog.releaseNotes : ""
    readonly property bool isDownloading: dialogAvailable && updateDialog.downloading
    readonly property bool hasProgress: dialogAvailable && updateDialog.progressVisible
    readonly property real updateProgress: dialogAvailable ? updateDialog.progress : 0
    readonly property string updateStatus: dialogAvailable ? updateDialog.statusText : ""
    readonly property bool isInstallComplete: dialogAvailable && updateDialog.installComplete
    readonly property string updateButtonLabel: dialogAvailable ? updateDialog.updateButtonText : ""

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_overlay"]
        opacity: 0.86
        MouseArea { anchors.fill: parent; onClicked: if (root.dialogAvailable) updateDialog.closeDialog() }
    }

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: Math.min(540, parent.width - Theme.spacingXxl * 2)
        height: Math.min(500, parent.height - Theme.spacingXxl * 2)
        radius: Theme.radiusLg
        color: root.colors["bg_elevated"]
        border.width: 1
        border.color: root.colors["border_focus"]

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.spacingLg
            spacing: Theme.spacingMd

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "new_releases"
                    font.family: root.iconFont
                    font.pixelSize: 30
                    color: root.colors["accent"]
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "Nueva versión disponible"
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: root.dialogCurrentVersion + "  →  " + root.dialogVersion
                        color: root.colors["accent"]
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.typeMono
                    }
                }
                Item {
                    width: 32; height: 32
                    Text { anchors.centerIn: parent; text: "close"; font.family: root.iconFont; font.pixelSize: 20; color: root.colors["text_secondary"] }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (root.dialogAvailable) updateDialog.closeDialog() }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.colors["border"] }

            Text {
                text: "Novedades en esta versión"
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                font.weight: Font.Medium
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                TextArea {
                    text: root.dialogReleaseNotes
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextArea.Wrap
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeBody
                    background: Rectangle { radius: Theme.radiusMd; color: root.colors["bg_surface"]; border.width: 1; border.color: root.colors["border"] }
                }
            }

            ColumnLayout {
                visible: root.hasProgress
                Layout.fillWidth: true
                spacing: Theme.spacingXs
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 6
                    radius: 3
                    color: root.colors["bg_surface"]
                    Rectangle {
                        width: parent.width * root.updateProgress / 100
                        height: parent.height
                        radius: parent.radius
                        color: root.colors["accent"]
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: root.updateStatus
                    wrapMode: Text.WordWrap
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeCaption
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                DialogButton {
                    text: "Ver en GitHub"
                    icon: "open_in_new"
                    onClicked: updateDialog.openGithub()
                }
                Item { Layout.fillWidth: true }
                DialogButton {
                    text: "Posponer"
                    enabled: !root.isDownloading
                    onClicked: if (root.dialogAvailable) updateDialog.closeDialog()
                }
                DialogButton {
                    text: root.updateButtonLabel
                    icon: root.isInstallComplete ? "check_circle" : "download"
                    primary: true
                    enabled: !root.isDownloading && !root.isInstallComplete
                    onClicked: if (root.dialogAvailable) updateDialog.startUpdate()
                }
            }
        }
    }

    component DialogButton: Rectangle {
        id: button
        property string text: ""
        property string icon: ""
        property bool primary: false
        signal clicked()
        implicitWidth: buttonText.implicitWidth + (icon.length > 0 ? 62 : 40)
        implicitHeight: 38
        radius: Theme.radiusMd
        color: primary ? root.colors["accent"] : (buttonMouse.containsMouse ? root.colors["bg_surface"] : root.colors["bg_elevated"])
        border.width: primary ? 0 : 1
        border.color: root.colors["border"]
        opacity: enabled ? 1 : 0.5
        Row {
            anchors.centerIn: parent
            spacing: Theme.spacingXs
            Text { visible: button.icon.length > 0; text: button.icon; font.family: root.iconFont; font.pixelSize: 18; color: button.primary ? root.colors["text_on_accent"] : root.colors["text_primary"] }
            Text { id: buttonText; text: button.text; font.family: Theme.fontFamily; font.pixelSize: Theme.typeLabel; font.weight: Font.DemiBold; color: button.primary ? root.colors["text_on_accent"] : root.colors["text_primary"] }
        }
        MouseArea { id: buttonMouse; anchors.fill: parent; hoverEnabled: true; enabled: button.enabled; cursorShape: Qt.PointingHandCursor; onClicked: button.clicked() }
    }
}
