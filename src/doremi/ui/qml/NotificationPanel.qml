import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // Compatibilidad con la isla actual; MainShell inyectará esta propiedad.
    property var notificationController: null
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_overlay"]
    }
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: root.colors["border"]
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            Layout.leftMargin: Theme.spacingMd
            Layout.rightMargin: Theme.spacingMd

            Label {
                text: "Notificaciones"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.weight: Font.Bold
                Layout.fillWidth: true
            }
            Label {
                visible: notificationController.hasHistory
                text: "Limpiar"
                color: clearMa.containsMouse ? root.accentColor : root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.weight: Font.Medium
                MouseArea {
                    id: clearMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: notificationController.clear_all()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: root.colors["border"]
        }

        BusyIndicator {
            visible: notificationController.loading
            running: notificationController.loading
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.spacingMd
        }

        // Empty state
        ColumnLayout {
            visible: !notificationController.loading && notificationController.isEmpty
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingSm

            Item { Layout.fillHeight: true }
            Text {
                text: "" // notifications
                font.family: root.iconFont
                font.pixelSize: 36
                color: root.colors["text_secondary"]
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                text: "No tienes notificaciones"
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeLabel
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        Flickable {
            visible: !notificationController.loading && !notificationController.isEmpty
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: contentCol.height
            clip: true
            flickableDirection: Flickable.VerticalFlick

            ColumnLayout {
                id: contentCol
                width: parent.width
                spacing: Theme.spacingXs

                // ── Descargas en curso ────────────────────────────────
                Label {
                    visible: notificationController.hasActive
                    text: "Descargas en curso"
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    Layout.topMargin: Theme.spacingSm
                    Layout.leftMargin: Theme.spacingSm
                }

                Repeater {
                    model: notificationController.active

                    delegate: Rectangle {
                        id: dlRow
                        required property string videoId
                        required property string title
                        required property string artist
                        required property double progress
                        required property string speed

                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: Theme.radiusMd
                        color: root.colors["bg_elevated"]
                        Layout.leftMargin: Theme.spacingXs
                        Layout.rightMargin: Theme.spacingXs

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingSm
                            spacing: Theme.spacingXxs

                            Label {
                                text: dlRow.title
                                color: root.colors["text_primary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeLabel
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Label {
                                text: dlRow.artist
                                color: root.colors["text_secondary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeCaption
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingSm
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 4
                                    radius: 2
                                    color: root.colors["bg_high"]
                                    Rectangle {
                                        width: parent.width * Math.max(0, Math.min(100, dlRow.progress)) / 100
                                        height: parent.height
                                        radius: 2
                                        color: root.accentColor
                                    }
                                }
                                Label {
                                    text: Math.round(dlRow.progress) + "%"
                                    color: root.accentColor
                                    font.family: Theme.fontMono
                                    font.pixelSize: 10
                                }
                                // Cancelar
                                Text {
                                    text: "" // close
                                    font.family: root.iconFont
                                    font.pixelSize: 14
                                    color: cancelMa.containsMouse ? root.colors["error"] : root.colors["text_secondary"]
                                    MouseArea {
                                        id: cancelMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: notificationController.cancel_download(dlRow.videoId)
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Nuevos lanzamientos ───────────────────────────────
                Label {
                    visible: notificationController.hasReleases
                    text: "Nuevos lanzamientos"
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    Layout.topMargin: Theme.spacingSm
                    Layout.leftMargin: Theme.spacingSm
                }

                Repeater {
                    model: notificationController.releases

                    delegate: Rectangle {
                        id: relRow
                        required property string videoId
                        required property string title
                        required property string artist
                        required property string artistId
                        required property string thumbnail
                        required property string timeAgo

                        Layout.fillWidth: true
                        Layout.preferredHeight: 64
                        radius: Theme.radiusMd
                        color: relMa.containsMouse ? root.colors["bg_high"] : "transparent"
                        Layout.leftMargin: Theme.spacingXs
                        Layout.rightMargin: Theme.spacingXs

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingSm
                            spacing: Theme.spacingSm

                            Rectangle {
                                Layout.preferredWidth: 44
                                Layout.preferredHeight: 44
                                radius: Theme.radiusSm
                                color: root.colors["bg_elevated"]
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    source: relRow.thumbnail
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                    visible: status === Image.Ready
                                }
                                Text {
                                    anchors.centerIn: parent
                                    visible: parent.children[0].status !== Image.Ready
                                    text: "" // music_note
                                    font.family: root.iconFont
                                    font.pixelSize: 18
                                    color: root.colors["text_secondary"]
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    text: relRow.title
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: relRow.artistId ? relRow.artist : (relRow.artist + " • " + relRow.timeAgo)
                                    color: artistMa.containsMouse && relRow.artistId ? root.accentColor : root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    MouseArea {
                                        id: artistMa
                                        anchors.fill: parent
                                        enabled: relRow.artistId !== ""
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: notificationController.open_artist(relRow.artist, relRow.artistId)
                                    }
                                }
                            }
                        }

                        MouseArea {
                            id: relMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: notificationController.play_release(relRow.videoId, relRow.title, relRow.artist, relRow.thumbnail)
                        }
                    }
                }

                // ── Historial ─────────────────────────────────────────
                Label {
                    visible: notificationController.hasHistory
                    text: "Historial"
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    Layout.topMargin: Theme.spacingSm
                    Layout.leftMargin: Theme.spacingSm
                }

                Repeater {
                    model: notificationController.history

                    delegate: Rectangle {
                        id: hRow
                        required property string title
                        required property string kind

                        Layout.fillWidth: true
                        Layout.preferredHeight: hLbl.implicitHeight + Theme.spacingMd
                        radius: Theme.radiusMd
                        color: root.colors["bg_elevated"]
                        Layout.leftMargin: Theme.spacingXs
                        Layout.rightMargin: Theme.spacingXs

                        Label {
                            id: hLbl
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: Theme.spacingSm
                            anchors.rightMargin: Theme.spacingSm
                            text: hRow.title
                            color: hRow.kind === "error" ? root.colors["error"] : root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Item { Layout.preferredHeight: Theme.spacingSm }
            }
        }
    }
}
