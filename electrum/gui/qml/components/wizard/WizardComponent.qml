import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

Pane {
    id: root
    signal next
    signal finish
    signal prev
    signal accept
    property var wizard_data : ({})
    property bool valid
    property bool last: false
    property string wizard_title: ''
    property string title: ''
    property bool securePage: false

    leftPadding: constants.paddingXLarge
    rightPadding: constants.paddingXLarge

    background: Rectangle {
        color: Material.dialogColor
        TapHandler {
            onTapped: root.forceActiveFocus()
        }
    }

    onAccept: {
        apply()
    }

    
    function apply() { }

    function checkIsLast() {
        apply()
        last = wizard.wiz.isLast(wizard_data)
    }

    Component.onCompleted: {
        
        
        
        
        
        Qt.callLater(checkIsLast)

        
        
        root.forceActiveFocus()
    }

}
