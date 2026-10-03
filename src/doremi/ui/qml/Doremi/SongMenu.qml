import QtQuick
import QtQuick.Controls
import Doremi 1.0

ContextMenu {
    id: root
    property bool liked: false
    property bool localTrack: false
    property bool hasArtist: false
    property bool hasAlbum: false
    property bool showPlay: true
    property bool showDetails: false
    property bool showLink: false
    property bool downloaded: false
    property bool showRemove: false
    property bool showQueueRemove: false
    signal action(string name)
    ContextMenuItem { text: "Reproducir ahora"; visible: root.showPlay; height: visible ? implicitHeight : 0; onTriggered: root.action("play") }
    ContextMenuItem { text: "Reproducir siguiente"; onTriggered: root.action("play_next") }
    ContextMenuItem { text: "Añadir a cola"; onTriggered: root.action("add_to_queue") }
    MenuSeparator {}
    ContextMenuItem { text: root.liked ? "Quitar Me gusta" : "Me gusta"; onTriggered: root.action("like") }
    ContextMenuItem { text: "Añadir a playlist"; onTriggered: root.action("add_to_playlist") }
    ContextMenuItem { text: "Descargar"; visible: !root.localTrack && !root.downloaded; height: visible ? implicitHeight : 0; onTriggered: root.action("download") }
    ContextMenuItem { text: "Eliminar descarga"; visible: !root.localTrack && root.downloaded; height: visible ? implicitHeight : 0; onTriggered: root.action("delete_download") }
    MenuSeparator { visible: root.hasArtist || root.hasAlbum || root.showDetails || (root.showLink && !root.localTrack) || root.showRemove || root.showQueueRemove; height: visible ? implicitHeight : 0 }
    ContextMenuItem { text: "Ir al artista"; visible: root.hasArtist; height: visible ? implicitHeight : 0; onTriggered: root.action("go_artist") }
    ContextMenuItem { text: "Ir al álbum"; visible: root.hasAlbum; height: visible ? implicitHeight : 0; onTriggered: root.action("go_album") }
    ContextMenuItem { text: "Detalles y créditos"; visible: root.showDetails; height: visible ? implicitHeight : 0; onTriggered: root.action("details") }
    ContextMenuItem { text: "Copiar enlace"; visible: root.showLink && !root.localTrack; height: visible ? implicitHeight : 0; onTriggered: root.action("copy_link") }
    ContextMenuItem { text: "Quitar de esta playlist"; visible: root.showRemove; height: visible ? implicitHeight : 0; onTriggered: root.action("remove") }
    ContextMenuItem { text: "Quitar de la cola"; visible: root.showQueueRemove; height: visible ? implicitHeight : 0; onTriggered: root.action("remove_from_queue") }
}
