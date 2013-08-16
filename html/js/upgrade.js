/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

JqueryClass('upgradeWindow', {
    init: function(options) {
	var self = $(this)

	var icon = options.icon
	var windowManager = options.windowManager
	self.data('icon', icon)
	self.data('windowManager', options.windowManager)
	self.data('uptodate', true)

	icon.statusTooltip()

	icon.click(function() {
	    self.upgradeWindow('open')
	})

	self.find('button').click(function() {
	    if (!confirm("The MOD softare will be upgraded. Any unsaved work will be lost. The upgrade can take several minutes, in which you may not be able to play or do anything else. Continue?"))
		return
	    var installer = new Installer({ 
		repository: PACKAGE_REPOSITORY,
		localServer: PACKAGE_SERVER_ADDRESS,
		reportStatus: function(status) { self.upgradeWindow('reportInstallationStatus', status) }
	    })
	    self.upgradeWindow('downloadStart')
	    installer.upgrade(function() { self.upgradeWindow('downloadEnd') })
	})

	self.upgradeWindow('check')
	self.hide()
    },

    open: function() {
	var self = $(this)
	if (!self.data('uptodate'))
	    self.show()
    },

    check: function() {
	var self = $(this)
	var icon = self.data('icon')
	try {
	    var installer = new Installer({ 
		repository: PACKAGE_REPOSITORY,
		localServer: PACKAGE_SERVER_ADDRESS
	    })
	} catch(err) {
	    icon.statusTooltip('message', 'Local upgrade server is offline')
	    return
	}
	icon.statusTooltip('message', 'Checking for updates...', true)
	installer.checkUpgrade(function(packages) {
	    if (packages.length == 0) {
		icon.statusTooltip('message', 'System is up-to-date', true)
		icon.statusTooltip('status', 'uptodate')
		self.data('uptodate', true)
		self.hide()
		return
	    }
	    icon.statusTooltip('status', 'update-available')
	    if (packages.length == 1)
		icon.statusTooltip('message', '1 software update available')
	    else
		icon.statusTooltip('message', sprintf('%d software updates available', packages.length))
	    var ul = self.find('ul')
	    ul.html('')
	    var i, pack
	    for (i=0; i<packages.length; i++) {
		pack = packages[i].replace(/^(.+)-([0-9.]+)-(\d+)-[^-]+.tar.xz$/, 
					   function(m, pack, version, release) {
					       return pack + ' v' + version + ' rel. ' + release
					   })
		$('<li>').html(pack).appendTo(ul)
	    }
	    self.data('uptodate', false)
	})
    },

    reportInstallationStatus: function(status) {
	var self = $(this)
	if (status.complete && status.numFile == status.totalFiles) {
	    self.find('.download-info').hide()
	    self.find('.download-start').hide()
	    self.find('.download-installing').show()
	    self.upgradeWindow('block')
	} else {
	    self.find('.download-info').show()
	    self.find('.download-start').hide()
	    self.find('.download-installing').hide()
	}
	self.find('.progressbar').width(self.find('.progressbar-wrapper').width() * status.percent / 100)
	self.find('.filename').html(status.currentFile)
	self.find('.file-number').html(status.numFile)
	self.find('.total-files').html(status.totalFiles)
    },

    downloadStart: function() {
	var self = $(this)
	self.find('.mod-upgrade-packages-list').hide()
	self.find('.download-progress').show()
	self.find('.download-info').hide()
	self.find('.download-installing').hide()
	self.find('.installation-checking').hide()
	self.find('.download-start').show()
	self.find('.progressbar').width(0)
    },

    downloadEnd: function() {
	var self = $(this)
	document.location.reload()
    },

    block: function() {
	var self = $(this)
	self.data('windowManager').closeWindows()
	var block = $('<div class="screen-disconnected">')
	$('body').append(block).css('overflow', 'hidden')
	block.width($(window).width() * 5)
	block.height($(window).height() * 5)
	block.css('margin-left', -$(window).width() * 2)
	$('#wrapper').css('z-index', -1)
    }
})