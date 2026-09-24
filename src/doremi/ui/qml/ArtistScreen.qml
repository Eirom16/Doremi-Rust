import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (ArtistViewModel) llegan por contexto.
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
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
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
                Layout.fillHeight: true
                visible: vm.loading
                spacing: Theme.spacingMd
                Item { Layout.preferredHeight: 120 }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: vm.loading
                }
                Item { Layout.fillHeight: true }
            }

            // ── No encontrado ─────────────────────────────────────────
            Label {
                visible: !vm.loading && !vm.found
                text: "Artista no encontrado"
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

                // Cover circular (paridad widgets)
                Item {
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 200

                    Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        color: root.colors["bg_elevated"]

                        Image {
                            id: coverImg
                            anchors.fill: parent
                            source: vm.thumbnail
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            visible: status === Image.Ready
                            layer.enabled: true
                            layer.effect: OpacityMask {
                                maskSource: Rectangle {
                                    width: 200; height: 200
                                    radius: 100
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: coverImg.status !== Image.Ready
                            text: "" // person
                            font.family: root.iconFont
                            font.pixelSize: 72
                            color: root.colors["text_secondary"]
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignBottom
                    spacing: Theme.spacingXs

                    Label {
                        text: "ARTISTA"
                        color: root.accentColor
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeCaption
                        font.weight: Font.Bold
                        font.letterSpacing: 1.5
                    }
                    Label {
                        text: vm.artistName
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeDisplay
                        font.weight: Font.Bold
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Label {
                        visible: vm.subscribers !== ""
                        text: vm.subscribers
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeBody
                    }

                    RowLayout {
                        spacing: Theme.spacingSm
                        Layout.topMargin: Theme.spacingSm

                        // Reproducir (accent pill)
                        Rectangle {
                            width: playLbl.implicitWidth + Theme.spacingLg * 2
                            height: 44
                            radius: Theme.radiusPill
                            enabled: vm.hasSongs
                            color: enabled ? (ma1.containsMouse ? root.colors["accent_bright"] : root.accentColor)
                                           : root.colors["bg_high"]

                            Row {
                                anchors.centerIn: parent
                                spacing: Theme.spacingXs
                                Text {
                                    text: "" // play_arrow
                                    font.family: root.iconFont
                                    font.pixelSize: 20
                                    color: root.colors["text_on_accent"]
                                }
                                Label {
                                    id: playLbl
                                    text: "Reproducir"
                                    color: root.colors["text_on_accent"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                }
                            }
                            MouseArea {
                                id: ma1
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                enabled: vm.hasSongs
                                onClicked: vm.play_all()
                            }
                        }

                        // Aleatorio (secundario)
                        Rectangle {
                            width: shufLbl.implicitWidth + Theme.spacingLg * 2
                            height: 44
                            radius: Theme.radiusPill
                            enabled: vm.hasSongs
                            color: ma2.containsMouse && enabled ? root.colors["bg_high"] : root.colors["bg_elevated"]
                            border.width: 1
                            border.color: ma2.containsMouse ? root.accentColor : root.colors["border"]

                            Row {
                                anchors.centerIn: parent
                                spacing: Theme.spacingXs
                                Text {
                                    text: "" // shuffle
                                    font.family: root.iconFont
                                    font.pixelSize: 18
                                    color: root.colors["text_primary"]
                                }
                                Label {
                                    id: shufLbl
                                    text: "Aleatorio"
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                }
                            }
                            MouseArea {
                                id: ma2
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                enabled: vm.hasSongs
                                onClicked: vm.play_shuffle()
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // ── Canciones ─────────────────────────────────────────────
            ColumnLayout {
                visible: !vm.loading && vm.found && vm.songs.rowCount() > 0
                Layout.fillWidth: true
                spacing: Theme.spacingXs

                Label {
                    text: "Canciones"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeHeading
                    font.weight: Font.DemiBold
                    Layout.bottomMargin: Theme.spacingXs
                }

                Repeater {
                    model: vm.songs

                    delegate: Rectangle {
                        id: songRow
                        required property int index
                        required property string title
                        required property string artist
                        required property string duration
                        required property string thumbnail

                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: Theme.radiusLg
                        color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"

                        // Fondo clickeable PRIMERO: queda debajo del menú.
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
                                Layout.preferredWidth: 52
                                Layout.preferredHeight: 52
                                radius: Theme.radiusMd
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
                                    font.pixelSize: 22
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
                                    text: songRow.artist
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            Label {
                                text: songRow.duration
                                color: root.colors["text_secondary"]
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.typeCaption
                                visible: songRow.duration !== ""
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
                            }
                        }
                    }
                }
            }

            // ── Álbumes ───────────────────────────────────────────────
            ColumnLayout {
                visible: !vm.loading && vm.found && vm.albums.rowCount() > 0
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                Label {
                    text: "Álbumes"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeHeading
                    font.weight: Font.DemiBold
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: Math.max(2, Math.floor(width / 190))
                    rowSpacing: Theme.spacingMd
                    columnSpacing: Theme.spacingMd

                    Repeater {
                        model: vm.albums

                        delegate: Rectangle {
                            id: albumCard
                            required property string title
                            required property string subtitle
                            required property string thumbnail
                            required property string navigate

                            Layout.fillWidth: true
                            Layout.preferredHeight: cardCol.implicitHeight + Theme.spacingSm * 2
                            radius: Theme.radiusLg
                            color: albumMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                            border.width: 1
                            border.color: albumMa.containsMouse ? root.colors["border_focus"] : root.colors["border"]

                            ColumnLayout {
                                id: cardCol
                                anchors.fill: parent
                                anchors.margins: Theme.spacingSm
                                spacing: Theme.spacingXs

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: width
                                    radius: Theme.radiusMd
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: albumCard.thumbnail
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
                                        font.pixelSize: 36
                                        color: root.colors["text_secondary"]
                                    }
                                }

                                Label {
                                    text: albumCard.title
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Label {
                                    visible: albumCard.subtitle !== ""
                                    text: albumCard.subtitle
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: albumMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (albumCard.navigate)
                                        vm.navigate(albumCard.navigate)
                                }
                            }
                        }
                    }
                }
            }

            // ── Artistas similares ────────────────────────────────────
            ColumnLayout {
                visible: !vm.loading && vm.found && vm.related.rowCount() > 0
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                Label {
                    text: "Artistas Similares"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeHeading
                    font.weight: Font.DemiBold
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    orientation: ListView.Horizontal
                    spacing: Theme.spacingMd
                    clip: true
                    model: vm.related

                    delegate: ColumnLayout {
                        id: relCard
                        required property string title
                        required property string thumbnail
                        required property string navigate

                        width: 140
                        spacing: Theme.spacingXs

                        Item {
                            Layout.preferredWidth: 140
                            Layout.preferredHeight: 140

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: root.colors["bg_elevated"]

                                Image {
                                    id: relImg
                                    anchors.fill: parent
                                    source: relCard.thumbnail
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                    visible: status === Image.Ready
                                    layer.enabled: true
                                    layer.effect: OpacityMask {
                                        maskSource: Rectangle {
                                            width: 140; height: 140
                                            radius: 70
                                        }
                                    }
                                }
                                Text {
                                    anchors.centerIn: parent
                                    visible: relImg.status !== Image.Ready
                                    text: "" // person
                                    font.family: root.iconFont
                                    font.pixelSize: 48
                                    color: root.colors["text_secondary"]
                                }
                            }

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: relMa.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                                border.width: 1
                                border.color: relMa.containsMouse ? root.accentColor : "transparent"
                            }

                            MouseArea {
                                id: relMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (relCard.navigate)
                                        vm.navigate(relCard.navigate)
                                }
                            }
                        }

                        Label {
                            text: relCard.title
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Medium
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
