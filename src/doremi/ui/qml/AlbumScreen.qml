import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (AlbumViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    Flickable {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        anchors.topMargin: Theme.spacingSm
        anchors.bottomMargin: 112
        contentWidth: width
        contentHeight: contentCol.height
        clip: true
        flickableDirection: Flickable.VerticalFlick

        ColumnLayout {
            id: contentCol
            width: parent.width
            spacing: Theme.spacingLg

            // ── Volver ────────────────────────────────────────────────
            Rectangle {
                Layout.preferredWidth: backLbl.implicitWidth + Theme.spacingMd * 2
                Layout.preferredHeight: 36
                radius: Theme.radiusSm
                color: backMa.containsMouse ? root.colors["bg_elevated"] : "transparent"

                Row {
                    anchors.centerIn: parent
                    spacing: Theme.spacingXxs
                    Text {
                        text: "" // arrow_back
                        font.family: root.iconFont
                        font.pixelSize: 16
                        color: root.colors["text_secondary"]
                    }
                    Label {
                        id: backLbl
                        text: "Volver"
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        font.weight: Font.Medium
                    }
                }
                MouseArea {
                    id: backMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.go_back()
                }
            }

            // ── Loading ───────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                visible: vm.loading
                spacing: Theme.spacingMd
                Item { Layout.preferredHeight: 120 }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: vm.loading
                }
            }

            // ── No encontrado ─────────────────────────────────────────
            Label {
                visible: !vm.loading && !vm.found
                text: "Álbum no encontrado"
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 120
            }

            // ── Hero ──────────────────────────────────────────────────
            RowLayout {
                visible: !vm.loading && vm.found
                Layout.fillWidth: true
                spacing: Theme.spacingXl

                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 200
                    radius: Theme.radiusMd
                    color: root.colors["bg_elevated"]
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: vm.thumbnail
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        visible: status === Image.Ready
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: parent.children[0].status !== Image.Ready
                        text: "" // album
                        font.family: root.iconFont
                        font.pixelSize: 72
                        color: root.colors["text_secondary"]
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignBottom
                    spacing: Theme.spacingXs

                    Label {
                        text: vm.typeLabel
                        color: root.accentColor
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeCaption
                        font.weight: Font.Bold
                        font.letterSpacing: 1.5
                    }
                    Label {
                        text: vm.title
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeDisplay
                        font.weight: Font.Bold
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Label {
                        text: vm.meta
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                    }

                    // ── Acciones ──────────────────────────────────────
                    RowLayout {
                        spacing: Theme.spacingSm
                        Layout.topMargin: Theme.spacingSm

                        HeroButton {
                            id: playBtn
                            primary: true
                            text: "Reproducir"
                            iconCode: "" // play_arrow
                            enabled: vm.hasTracks
                            onClicked: vm.play_all()
                        }
                        HeroButton {
                            primary: false
                            text: "Aleatorio"
                            iconCode: "" // shuffle
                            enabled: vm.hasTracks
                            onClicked: vm.play_shuffle()
                        }

                        // Descarga: estados
                        Label {
                            visible: vm.dlState === "full"
                            text: "Disponible sin conexión"
                            color: root.accentColor
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Bold
                            Layout.leftMargin: Theme.spacingSm
                        }

                        ColumnLayout {
                            visible: vm.dlState !== "full" && vm.dlState !== ""
                            spacing: Theme.spacingXs

                            HeroButton {
                                primary: false
                                text: vm.dlText
                                iconCode: "" // download
                                enabled: vm.dlState !== "active"
                                onClicked: {
                                    vm.download_album()
                                    vm.mark_downloader_feedback()
                                }
                            }

                            Rectangle {
                                visible: vm.dlState === "active"
                                Layout.preferredWidth: 180
                                Layout.preferredHeight: 4
                                radius: 2
                                color: root.colors["bg_high"]

                                Rectangle {
                                    width: parent.width * vm.dlPercent / 100
                                    height: parent.height
                                    radius: 2
                                    color: root.accentColor
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // ── Tracks ────────────────────────────────────────────────
            ColumnLayout {
                visible: !vm.loading && vm.found && vm.hasTracks
                Layout.fillWidth: true
                spacing: Theme.spacingXs
                Layout.topMargin: Theme.spacingSm

                Repeater {
                    model: vm.tracks

                    delegate: Rectangle {
                        id: row
                        required property int index
                        required property string title
                        required property string artist
                        required property string duration
                        required property string thumbnail
                        required property bool isDownloaded

                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: Theme.radiusLg
                        color: rowMa.containsMouse ? root.colors["bg_high"] : "transparent"

                        // Fondo clickeable PRIMERO: debajo de botones.
                        MouseArea {
                            id: rowMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (mouse) => {
                                if (mouse.button === Qt.LeftButton)
                                    vm.play_at(row.index)
                                else
                                    rowMenu.popup()
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSm
                            anchors.rightMargin: Theme.spacingSm
                            spacing: Theme.spacingMd

                            Rectangle {
                                Layout.preferredWidth: 52
                                Layout.preferredHeight: 52
                                radius: Theme.radiusMd
                                color: root.colors["bg_elevated"]
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    source: row.thumbnail
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
                                    font.pixelSize: 22
                                    color: root.colors["text_secondary"]
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    text: row.title
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeBody
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: row.artist
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            // Badge descargada
                            Text {
                                visible: row.isDownloaded
                                text: "" // check_circle
                                font.family: root.iconFont
                                font.pixelSize: 16
                                color: root.accentColor
                            }

                            Label {
                                text: row.duration
                                color: root.colors["text_secondary"]
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.typeCaption
                                visible: row.duration !== ""
                            }

                            Menu {
                                id: rowMenu
                                MenuItem {
                                    text: "Reproducir siguiente"
                                    onTriggered: vm.track_action(row.index, "play_next")
                                }
                                MenuItem {
                                    text: "Añadir a la cola"
                                    onTriggered: vm.track_action(row.index, "add_to_queue")
                                }
                                MenuItem {
                                    text: "Me gusta"
                                    onTriggered: vm.track_action(row.index, "like")
                                }
                                MenuItem {
                                    text: "Añadir a playlist"
                                    onTriggered: vm.track_action(row.index, "add_to_playlist")
                                }
                                MenuItem {
                                    text: "Descargar"
                                    onTriggered: vm.track_action(row.index, "download")
                                }
                                MenuItem {
                                    visible: row.isDownloaded
                                    text: "Eliminar descarga"
                                    onTriggered: vm.track_action(row.index, "delete_download")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
