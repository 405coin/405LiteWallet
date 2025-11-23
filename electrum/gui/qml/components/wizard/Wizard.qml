import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import org.electrum 1.0

import "../controls"

ElDialog {
    id: wizard
    focus: true

    width: parent.width
    height: parent.height

    padding: 0

    title: (pages.currentItem.wizard_title ? pages.currentItem.wizard_title : wizardTitle) +
        (pages.currentItem.title ? ' - ' + pages.currentItem.title : '')
    iconSource: '../../../icons/electrum.png'

    
    
    closePolicy: Popup.NoAutoClose

    property string wizardTitle

    property var wizard_data
    property alias pages: pages
    property QtObject wiz
    property alias finishButtonText: finishButton.text

    function doClose() {
        if (pages.currentIndex == 0)
            reject()
        else
            pages.prev()
    }

    function _setWizardData(wdata) {
        wizard_data = {}
        Object.assign(wizard_data, wdata) 
        
    }

    
    
    
    
    
    function _loadNextComponent(view, wdata={}) {
        
        while (pages.contentChildren[pages.currentIndex+1]) {
            pages.takeItem(pages.currentIndex+1).destroy()
        }

        var url = Qt.resolvedUrl(wiz.viewToComponent(view))
        var comp = Qt.createComponent(url)
        if (comp.status == Component.Error) {
            console.log(comp.errorString())
            return null
        }

        
        var wdata_copy={}
        Object.assign(wdata_copy, wdata)
        var page = comp.createObject(pages, {wizard_data: wdata_copy})
        page.validChanged.connect(function() {
            if (page != pages.currentItem)
                return
            pages.pagevalid = page.valid
        })
        page.lastChanged.connect(function() {
            if (page != pages.currentItem)
                return
            pages.lastpage = page.last
        })
        page.next.connect(function() {
            var newview = wiz.submit(page.wizard_data)
            if (newview.view) {
                console.log('next view: ' + newview.view)
                var newpage = _loadNextComponent(newview.view, newview.wizard_data)
            } else {
                console.log('END')
            }
        })
        page.finish.connect(function() {
            
            var newview = wiz.submit(page.wizard_data)
            _setWizardData(newview.wizard_data)
            console.log('wizard finished')
            
            wizard.doAccept()
        })
        page.prev.connect(function() {
            var wdata = wiz.prev()
        })

        pages.pagevalid = page.valid
        pages.lastpage = page.last

        return page
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        
        Keys.onReleased: {
            if (event.key == Qt.Key_Back) {
                console.log("Back button within wizard")
                app.close() 
            }
        }

        SwipeView {
            id: pages
            Layout.fillWidth: true
            Layout.fillHeight: true

            interactive: false

            clip:true

            function prev() {
                currentItem.prev()
                currentIndex = currentIndex - 1
                _setWizardData(pages.contentChildren[currentIndex].wizard_data)
                pages.pagevalid = pages.contentChildren[currentIndex].valid
                pages.lastpage = pages.contentChildren[currentIndex].last

            }

            function next() {
                currentItem.accept()
                _setWizardData(pages.contentChildren[currentIndex].wizard_data)
                currentItem.next()
                currentIndex = currentIndex + 1
            }

            function finish() {
                currentItem.accept()
                _setWizardData(pages.contentChildren[currentIndex].wizard_data)
                currentItem.finish()
            }

            property bool pagevalid: false
            property bool lastpage: false

            Component.onCompleted: {
                _setWizardData({})
            }

            Binding {
                target: AppController
                property: 'secureWindow'
                value: pages.contentChildren[pages.currentIndex].securePage
            }
        }

        ButtonContainer {
            Layout.fillWidth: true

            FlatButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                visible: pages.currentIndex == 0
                text: qsTr("Cancel")
                onClicked: wizard.doReject()
            }
            FlatButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                visible: pages.currentIndex > 0
                text: qsTr('Back')
                onClicked: pages.prev()
            }
            FlatButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: qsTr("Next")
                visible: !pages.lastpage
                enabled: pages.pagevalid
                onClicked: pages.next()
            }
            FlatButton {
                id: finishButton
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: qsTr("Finish")
                visible: pages.lastpage
                enabled: pages.pagevalid
                onClicked: pages.finish()
            }
        }
    }

}
