import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    property var screenVm: null

    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    Flickable {
        id: flickable
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingMd
        anchors.rightMargin: Theme.spacingMd
        anchors.topMargin: Theme.spacingSm
        // Inicio conserva 100% de la altura: el mini-player es una capa
        // flotante y no debe recortar la vista ni crear una franja vacía.
        anchors.bottomMargin: 0
        contentHeight: contentCol.height + Theme.spacingSm
        clip: true
        flickableDirection: Flickable.VerticalFlick

        ColumnLayout {
            id: contentCol
            width: parent.width
            spacing: Theme.spacingSm

            // ── Loading state ──────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: screenVm.loading
                spacing: Theme.spacingMd
                Item { Layout.fillHeight: true }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: screenVm.loading
                }
                Label {
                    text: "Cargando inicio…"
                    color: root.colors["text_secondary"]
                    font.pixelSize: Theme.typeBody
                    Layout.alignment: Qt.AlignHCenter
                }
                Item { Layout.fillHeight: true }
            }

            // ── Greeting ──────────────────────────────────────────────
            Label {
                visible: !screenVm.loading
                text: screenVm.greeting
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeDisplay * 0.9
                font.weight: Font.DemiBold
                font.letterSpacing: -0.3
                Layout.fillWidth: true
            }

            // ── Spotlight Banner ──────────────────────────────────────
            Rectangle {
                visible: !screenVm.loading && screenVm.hasSpotlight
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                radius: Theme.radiusLg
                color: "transparent"

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusLg
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: root.colors["bg_surface"] }
                        GradientStop { position: 0.5; color: root.colors["bg_elevated"] }
                        GradientStop { position: 1.0; color: root.colors["accent_dim"] }
                    }
                    border.width: 1
                    border.color: root.colors["border"]
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingLg
                    spacing: Theme.spacingLg

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Theme.spacingXs

                        Item { Layout.fillHeight: true }

                        Label {
                            text: "DESTACADO"
                            color: root.colors["accent"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeCaption
                            font.weight: Font.Bold
                            font.letterSpacing: 1.5
                        }

                        Label {
                            text: screenVm.spotTitle
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: 22
                            font.weight: Font.ExtraBold
                            font.letterSpacing: -0.3
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Label {
                            text: screenVm.spotSubtitle
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Item { Layout.preferredHeight: 6 }

                        RowLayout {
                            spacing: Theme.spacingSm

                            Rectangle {
                                width: playBtnLabel.implicitWidth + Theme.spacingLg * 2
                                height: 34
                                radius: Theme.radiusPill
                                color: playBtnMa.containsMouse ? root.colors["accent_bright"] : root.colors["accent"]

                                Label {
                                    id: playBtnLabel
                                    anchors.centerIn: parent
                                    text: "Reproducir"
                                    color: root.colors["text_on_accent"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    id: playBtnMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (screenVm.spotNavigate) screenVm.navigate(screenVm.spotNavigate)
                                    }
                                }
                            }

                            Rectangle {
                                width: exploreBtnLabel.implicitWidth + Theme.spacingLg * 2
                                height: 34
                                radius: Theme.radiusPill
                                color: "transparent"
                                border.width: 1
                                border.color: root.colors["border"]

                                Label {
                                    id: exploreBtnLabel
                                    anchors.centerIn: parent
                                    text: "Explorar"
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (screenVm.spotNavigate) screenVm.navigate(screenVm.spotNavigate)
                                    }
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }
                    }

                    // Artwork thumbnail
                    Rectangle {
                        Layout.preferredWidth: 140
                        Layout.preferredHeight: 140
                        Layout.alignment: Qt.AlignVCenter
                        radius: Theme.radiusLg
                        color: root.colors["bg_high"]
                        clip: true

                        Image {
                            id: spotlightImg
                            anchors.fill: parent
                            source: screenVm.spotThumbnail
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            visible: status === Image.Ready
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: spotlightImg.status !== Image.Ready
                            text: "\u{e405}" // music_note
                            font.family: root.iconFont
                            font.pixelSize: 48
                            color: root.colors["text_secondary"]
                        }
                    }
                }
            }

            // ── Quick Access Grid ─────────────────────────────────────
            GridLayout {
                visible: !screenVm.loading && screenVm.tiles.rowCount() > 0
                Layout.fillWidth: true
                columns: 3
                rowSpacing: Theme.spacingXs
                columnSpacing: Theme.spacingSm

                Repeater {
                    model: screenVm.tiles

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 60
                        radius: Theme.radiusLg
                        color: tileMa.containsMouse ? root.colors["bg_elevated"] : root.colors["bg_surface"]
                        border.width: 1
                        border.color: tileMa.containsMouse ? root.colors["border_focus"] : root.colors["border"]

                        property bool hovered: tileMa.containsMouse
                                               || tilePlayMa.containsMouse
                                               || tileMenuMa.containsMouse

                        // Fondo clickeable: PRIMERO para quedar debajo de los
                        // botones (el último hijo recibe los eventos encima).
                        MouseArea {
                            id: tileMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton
                            onClicked: screenVm.play_tile(index)
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSm
                            anchors.rightMargin: Theme.spacingSm
                            spacing: Theme.spacingSm

                            Rectangle {
                                Layout.preferredWidth: 44
                                Layout.preferredHeight: 44
                                radius: Theme.radiusMd
                                color: root.colors["bg_high"]
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    source: model.thumbnail
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                    visible: status === Image.Ready
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: parent.children[0].status !== Image.Ready
                                    text: "\u{e405}" // library_music
                                    font.family: root.iconFont
                                    font.pixelSize: 22
                                    color: root.colors["text_secondary"]
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1

                                Label {
                                    text: model.title
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: -0.2
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            // Play button (visible on hover)
                            Rectangle {
                                width: 32; height: 32; radius: 16
                                color: tilePlayMa.containsMouse ? root.colors["accent_bright"] : root.colors["accent"]
                                opacity: hovered ? 1.0 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 150 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "\u{e037}" // play_arrow
                                    font.family: root.iconFont
                                    font.pixelSize: 18
                                    color: root.colors["text_on_accent"]
                                }
                                MouseArea {
                                    id: tilePlayMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: screenVm.play_tile(index)
                                }
                            }

                            // Menu button
                            Rectangle {
                                width: 32; height: 32; radius: 16
                                color: tileMenuMa.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                                opacity: hovered ? 1.0 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 150 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "\u{e5d3}" // more_vert
                                    font.family: root.iconFont
                                    font.pixelSize: 18
                                    color: root.colors["text_secondary"]
                                }
                                MouseArea {
                                    id: tileMenuMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: tileMenu.popup()
                                }

                                ContextMenu {
                                    id: tileMenu
                                    ContextMenuItem {
                                        text: "Reproducir siguiente"
                                        onTriggered: screenVm.tile_action(index, "play_next")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a la cola"
                                        onTriggered: screenVm.tile_action(index, "add_to_queue")
                                    }
                                    ContextMenuItem {
                                        text: "Me gusta"
                                        onTriggered: screenVm.tile_action(index, "like")
                                    }
                                    ContextMenuItem {
                                        text: "Añadir a playlist"
                                        onTriggered: screenVm.tile_action(index, "add_to_playlist")
                                    }
                                    ContextMenuItem {
                                        text: "Descargar"
                                        onTriggered: screenVm.tile_action(index, "download")
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Section title ─────────────────────────────────────────
            Label {
                visible: !screenVm.loading && (screenVm.horizontal.rowCount() > 0 || screenVm.songs.rowCount() > 0)
                text: "Recomendaciones para ti"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeHeading
                font.weight: Font.DemiBold
                font.letterSpacing: -0.2
                Layout.fillWidth: true
                Layout.topMargin: Theme.spacingSm
            }

            // ── Rail horizontales (una fila por sección) ─────────────
            Repeater {
                model: screenVm.sections

                delegate: ColumnLayout {
                    id: sectionBlock
                    required property string sectionTitle
                    required property var items

                    Layout.fillWidth: true
                    spacing: Theme.spacingXs
                    Layout.topMargin: Theme.spacingSm

                    Label {
                        text: sectionBlock.sectionTitle
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.DemiBold
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 196
                        orientation: ListView.Horizontal
                        model: sectionBlock.items
                        clip: true
                        spacing: Theme.spacingSm
                        interactive: contentWidth > width
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            id: hCard
                            required property var modelData

                            width: 164
                            height: ListView.view.height
                            radius: Theme.radiusLg
                            color: hCardMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                            border.width: 1
                            border.color: hCardMa.containsMouse ? root.colors["border_focus"] : root.colors["border"]

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingSm
                                spacing: Theme.spacingXs

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: Theme.radiusMd
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: hCard.modelData.thumbnail_url || ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                        visible: status === Image.Ready
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: parent.children[0].status !== Image.Ready
                                        text: "\u{e405}" // music_note
                                        font.family: root.iconFont
                                        font.pixelSize: 32
                                        color: root.colors["text_secondary"]
                                    }
                                }

                                Label {
                                    text: hCard.modelData.item_title || ""
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                Label {
                                    visible: text !== ""
                                    text: hCard.modelData.subtitle || ""
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: hCardMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var nav = hCard.modelData.navigate || ""
                                    if (nav) screenVm.navigate(nav)
                                }
                            }
                        }

                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }

            // ── Song grid ─────────────────────────────────────────────
            Repeater {
                model: screenVm.songs
                delegate: Rectangle {
                    required property string title
                    required property string artist
                    required property string duration
                    required property string thumbnail
                    required property string videoId
                    required property bool isLiked
                    required property int index

                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    radius: Theme.radiusLg
                    color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"

                    // Fondo clickeable PRIMERO: queda debajo de play/menú.
                    MouseArea {
                        id: songMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: (mouse) => {
                            if (mouse.button === Qt.LeftButton) {
                                screenVm.play_at(index)
                            } else {
                                songCtxMenu.popup()
                            }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingSm
                        anchors.rightMargin: Theme.spacingSm
                        spacing: Theme.spacingMd

                        // Artwork
                        Rectangle {
                            Layout.preferredWidth: 52
                            Layout.preferredHeight: 52
                            radius: Theme.radiusMd
                            color: root.colors["bg_elevated"]
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: thumbnail
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: status === Image.Ready
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: parent.children[0].status !== Image.Ready
                                text: "\u{e405}"
                                font.family: root.iconFont
                                font.pixelSize: 24
                                color: root.colors["text_secondary"]
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Label {
                                text: title
                                color: root.colors["text_primary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeBody
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Label {
                                text: artist
                                color: root.colors["text_secondary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeLabel
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        // Duration
                        Label {
                            text: duration
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.typeCaption
                            visible: duration !== ""
                        }

                        // Play button on hover
                        Rectangle {
                            width: 36; height: 36; radius: 18
                            readonly property bool rowHovered: songMa.containsMouse
                                || songPlayMa.containsMouse || songMenuMa.containsMouse
                            color: songPlayMa.containsMouse ? root.colors["accent"] : "transparent"
                            opacity: rowHovered ? 1.0 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 120 } }

                            Text {
                                anchors.centerIn: parent
                                text: "\u{e037}"
                                font.family: root.iconFont
                                font.pixelSize: 22
                                color: root.colors["text_on_accent"]
                            }
                            MouseArea {
                                id: songPlayMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: screenVm.play_at(index)
                            }
                        }

                        // Menu
                        Rectangle {
                            width: 36; height: 36; radius: 18
                            color: songMenuMa.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                            opacity: (songMa.containsMouse || songMenuMa.containsMouse) ? 1.0 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 120 } }

                            Text {
                                anchors.centerIn: parent
                                text: "\u{e5d3}"
                                font.family: root.iconFont
                                font.pixelSize: 20
                                color: root.colors["text_secondary"]
                            }
                            MouseArea {
                                id: songMenuMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: songCtxMenu.popup()
                            }

                            ContextMenu {
                                id: songCtxMenu
                                ContextMenuItem {
                                    text: "Reproducir siguiente"
                                    onTriggered: screenVm.song_action(index, "play_next")
                                }
                                ContextMenuItem {
                                    text: "Añadir a la cola"
                                    onTriggered: screenVm.song_action(index, "add_to_queue")
                                }
                                ContextMenuItem {
                                    text: "Me gusta"
                                    onTriggered: screenVm.song_action(index, "like")
                                }
                                ContextMenuItem {
                                    text: "Añadir a playlist"
                                    onTriggered: screenVm.song_action(index, "add_to_playlist")
                                }
                                ContextMenuItem {
                                    text: "Descargar"
                                    onTriggered: screenVm.song_action(index, "download")
                                }
                                ContextMenuItem {
                                    text: "Ir al artista"
                                    onTriggered: screenVm.song_action(index, "go_artist")
                                }
                            }
                        }
                    }
                }
            }

            // ── Empty offline state ───────────────────────────────────
            Label {
                visible: !screenVm.loading && screenVm.horizontal.rowCount() === 0 && screenVm.songs.rowCount() === 0 && screenVm.tiles.rowCount() === 0
                text: "Aún no hay música disponible sin conexión"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeHeading
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                Layout.topMargin: Theme.spacingSm
            }

            Label {
                visible: !screenVm.loading && screenVm.horizontal.rowCount() === 0 && screenVm.songs.rowCount() === 0 && screenVm.tiles.rowCount() === 0
                text: "Conéctate una vez para que Doremi prepare y rote tus recomendaciones."
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
                Layout.fillWidth: true
                Layout.topMargin: Theme.spacingSm
            }
        }
    }
}
