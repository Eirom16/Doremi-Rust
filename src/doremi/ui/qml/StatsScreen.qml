import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (StatsViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    function playsText(n) {
        return n > 1 ? n + " veces" : "1 vez"
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    Flickable {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        anchors.topMargin: Theme.spacingMd
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
        contentWidth: width
        contentHeight: contentCol.height
        clip: true
        flickableDirection: Flickable.VerticalFlick

        ColumnLayout {
            id: contentCol
            width: parent.width
            spacing: Theme.spacingLg

            // ── Header ────────────────────────────────────────────────
            ColumnLayout {
                spacing: Theme.spacingXxs
                Label {
                    text: "Tus Estadísticas"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeDisplay * 0.75
                    font.weight: Font.Bold
                }
                Label {
                    text: "Analiza tus hábitos musicales y descubre tus canciones favoritas"
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeBody
                }
            }

            // ── Loading ───────────────────────────────────────────────
            ColumnLayout {
                visible: vm.loading
                Layout.fillWidth: true
                spacing: Theme.spacingMd
                Item { Layout.preferredHeight: 80 }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: vm.loading
                }
            }

            // ── Cards ─────────────────────────────────────────────────
            RowLayout {
                visible: !vm.loading
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Repeater {
                    model: [
                        { "icon": "schedule", "value": vm.timeListened, "label": "Tiempo Escuchado" },
                        { "icon": "play_arrow", "value": "" + vm.totalPlays, "label": "Total Reproducidas" },
                        { "icon": "artist", "value": "" + vm.uniqueArtists, "label": "Artistas Únicos" }
                    ]

                    delegate: Rectangle {
                        id: statCard
                        required property var modelData

                        Layout.fillWidth: true
                        Layout.preferredHeight: 84
                        radius: Theme.radiusLg
                        color: root.colors["bg_elevated"]
                        border.width: 1
                        border.color: root.colors["border"]

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingMd
                            spacing: Theme.spacingMd

                            Rectangle {
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 48
                                radius: 24
                                color: root.accentWithAlpha(0.15)

                                Text {
                                    anchors.centerIn: parent
                                    text: {
                                        if (statCard.modelData.icon === "schedule") return ""
                                        if (statCard.modelData.icon === "play_arrow") return ""
                                        if (statCard.modelData.icon === "artist") return ""
                                        return ""
                                    }
                                    font.family: root.iconFont
                                    font.pixelSize: 22
                                    color: root.accentColor
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Label {
                                    text: statCard.modelData.value
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 20
                                    font.weight: Font.Bold
                                }
                                Label {
                                    text: statCard.modelData.label
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.Medium
                                }
                            }
                        }
                    }
                }
            }

            // ── Columnas: top songs + chart ───────────────────────────
            RowLayout {
                visible: !vm.loading
                Layout.fillWidth: true
                spacing: Theme.spacingLg

                // Top 5 canciones
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: Theme.spacingSm

                    Label {
                        text: "Tus 5 Más Escuchadas"
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.Bold
                    }

                    Label {
                        visible: vm.topSongs.rowCount() === 0
                        text: "No hay suficientes reproducciones registradas."
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        Layout.preferredWidth: 320
                        horizontalAlignment: Text.AlignHCenter
                        Layout.topMargin: Theme.spacingLg
                    }

                    Repeater {
                        model: vm.topSongs

                        delegate: Rectangle {
                            id: songRow
                            required property int index
                            required property string title
                            required property string artist
                            required property int plays
                            required property string thumbnail

                            Layout.fillWidth: true
                            Layout.preferredHeight: 64
                            radius: Theme.radiusLg
                            color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"

                            MouseArea {
                                id: songMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.LeftButton)
                                        vm.play_at(songRow.index)
                                    else
                                        songMenu.popup()
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingMd

                                Rectangle {
                                    Layout.preferredWidth: 48
                                    Layout.preferredHeight: 48
                                    radius: Theme.radiusSm
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: songRow.thumbnail
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
                                        font.pixelSize: 20
                                        color: root.colors["text_secondary"]
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Label {
                                        text: songRow.title
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeBody
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: songRow.artist + " — " + root.playsText(songRow.plays)
                                        color: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeLabel
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                ContextMenu {
                                    id: songMenu
                                    ContextMenuItem {
                                        text: "Reproducir siguiente"
                                        onTriggered: vm.song_action(songRow.index, "play_next")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a la cola"
                                        onTriggered: vm.song_action(songRow.index, "add_to_queue")
                                    }
                                    ContextMenuItem {
                                        text: "Me gusta"
                                        onTriggered: vm.song_action(songRow.index, "like")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a playlist"
                                        onTriggered: vm.song_action(songRow.index, "add_to_playlist")
                                    }
                                    ContextMenuItem {
                                        text: "Descargar"
                                        onTriggered: vm.song_action(songRow.index, "download")
                                    }
                                    ContextMenuItem {
                                        text: "Ir al artista"
                                        onTriggered: vm.song_action(songRow.index, "go_artist")
                                    }
                                }
                            }
                        }
                    }
                }

                // Gráfica semanal
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: Theme.spacingSm

                    Label {
                        text: "Actividad de Escucha"
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.Bold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 280
                        radius: Theme.radiusLg
                        color: root.colors["bg_elevated"]
                        border.width: 1
                        border.color: root.colors["border"]

                        Label {
                            visible: vm.chartMax === 0
                            anchors.centerIn: parent
                            text: "Sin datos suficientes para graficar"
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingLg
                            anchors.bottomMargin: Theme.spacingLg + Theme.spacingMd
                            visible: vm.chartMax > 0
                            spacing: Theme.spacingSm

                            Repeater {
                                model: vm.chart

                                delegate: ColumnLayout {
                                    id: barCol
                                    required property string day
                                    required property int count

                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 0

                                    // Valor encima
                                    Label {
                                        Layout.fillWidth: true
                                        text: barCol.count > 0 ? String(barCol.count) : ""
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeCaption
                                        font.weight: Font.Bold
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Item { Layout.fillHeight: true }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: {
                                            var avail = barCol.height - 40
                                            if (vm.chartMax <= 0) return 0
                                            return Math.max(4, avail * barCol.count / vm.chartMax)
                                        }
                                        radius: Theme.radiusSm
                                        color: root.accentColor
                                        opacity: barHover.hovered ? 1.0 : 0.75

                                        HoverHandler { id: barHover }

                                        Behavior on Layout.preferredHeight {
                                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                                        }
                                    }
                                }
                            }
                        }

                        // Fila de etiquetas de día
                        RowLayout {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: Theme.spacingLg
                            anchors.topMargin: 0
                            spacing: Theme.spacingSm

                            Repeater {
                                model: vm.chart
                                delegate: Label {
                                    required property string day
                                    Layout.fillWidth: true
                                    text: day
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
