(function () {
  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function wsUrl(basePath) {
    var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    return protocol + window.location.host + basePath;
  }

  function safeJsonParse(value, fallback) {
    try {
      return JSON.parse(value);
    } catch (error) {
      return fallback;
    }
  }

  function formatSender(role, name) {
    if (name) return name;
    return role === 'admin' ? 'Support' : 'You';
  }

  function scrollThreadToBottom(thread) {
    if (!thread) return;
    thread.scrollTop = thread.scrollHeight;
  }

  function autosizeTextarea(textarea, maxHeight) {
    if (!textarea) return;
    var limit = Number(maxHeight) || 160;
    textarea.style.height = 'auto';
    if (textarea.scrollHeight > limit) {
      textarea.style.height = limit + 'px';
      textarea.style.overflowY = 'auto';
    } else {
      textarea.style.height = textarea.scrollHeight + 'px';
      textarea.style.overflowY = 'hidden';
    }
  }

  function bindAutosizeTextarea(textarea, maxHeight) {
    if (!textarea) return;
    var run = function () {
      autosizeTextarea(textarea, maxHeight);
    };
    textarea.addEventListener('input', run);
    textarea.addEventListener('change', run);
    textarea.addEventListener('focus', run);
    run();
  }

  function renderMessages(thread, messages, currentRole) {
    if (!thread) return;
    thread.innerHTML = '';
    if (!messages || !messages.length) {
      thread.innerHTML = '<div class="chat-empty">Start the conversation below.</div>';
      return;
    }
    messages.forEach(function (message) {
      var bubble = document.createElement('div');
      bubble.className = 'chat-bubble ' + (message.sender_role || 'client') + ' ' + ((message.sender_role || 'client') === 'admin' ? 'outgoing' : 'incoming');
      var meta = document.createElement('div');
      meta.className = 'chat-bubble-meta';
      var who = document.createElement('strong');
      who.textContent = formatSender(message.sender_role, message.sender_name);
      var time = document.createElement('span');
      time.textContent = message.time_label || '';
      meta.appendChild(who);
      meta.appendChild(time);
      var text = document.createElement('div');
      text.className = 'chat-bubble-text';
      text.textContent = message.content || '';
      bubble.appendChild(meta);
      bubble.appendChild(text);
      if (message.attachment_url) {
        var media = document.createElement('div');
        media.className = 'chat-bubble-image';
        var img = document.createElement('img');
        img.src = message.attachment_url;
        img.alt = message.attachment_name || 'Chat attachment';
        media.appendChild(img);
        bubble.appendChild(media);
      }
      thread.appendChild(bubble);
    });
    scrollThreadToBottom(thread);
  }

  function appendMessage(thread, message) {
    if (!thread) return;
    var empty = thread.querySelector('.chat-empty');
    if (empty) empty.remove();
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + (message.sender_role || 'client') + ' ' + ((message.sender_role || 'client') === 'admin' ? 'outgoing' : 'incoming');
    var meta = document.createElement('div');
    meta.className = 'chat-bubble-meta';
    var who = document.createElement('strong');
    who.textContent = formatSender(message.sender_role, message.sender_name);
    var time = document.createElement('span');
    time.textContent = message.time_label || '';
    meta.appendChild(who);
    meta.appendChild(time);
    var text = document.createElement('div');
    text.className = 'chat-bubble-text';
    text.textContent = message.content || '';
    bubble.appendChild(meta);
    bubble.appendChild(text);
    if (message.attachment_url) {
      var media = document.createElement('div');
      media.className = 'chat-bubble-image';
      var img = document.createElement('img');
      img.src = message.attachment_url;
      img.alt = message.attachment_name || 'Chat attachment';
      media.appendChild(img);
      bubble.appendChild(media);
    }
    thread.appendChild(bubble);
    scrollThreadToBottom(thread);
  }

  function setBadge(badge, value) {
    if (!badge) return;
    var total = Math.max(0, Number(value) || 0);
    badge.textContent = String(total);
    badge.style.display = total > 0 ? 'inline-flex' : 'none';
  }

  function initWidget(widget) {
    var panel = widget.querySelector('[data-chat-panel]');
    var toggleButtons = widget.querySelectorAll('[data-chat-toggle]');
    var thread = widget.querySelector('[data-chat-thread]');
    var composeForm = widget.querySelector('[data-chat-compose]');
    var input = widget.querySelector('[data-chat-input]');
    var attachmentInput = widget.querySelector('[data-chat-attachment]');
    var attachButton = widget.querySelector('[data-chat-attach]');
    var attachmentPreview = widget.querySelector('[data-chat-attachment-preview]');
    var badge = widget.querySelector('[data-chat-unread]');
    var unreadBanner = widget.querySelector('[data-chat-unread-banner]');
    var prechat = widget.querySelector('[data-chat-prechat]');
    var nameInput = widget.querySelector('[data-chat-name]');
    var emailInput = widget.querySelector('[data-chat-email]');
    var subtitle = widget.querySelector('[data-chat-subtitle]');
    var csrfInput = widget.querySelector('[data-chat-csrf] input[name="csrfmiddlewaretoken"]');
    var startUrl = widget.getAttribute('data-chat-start-url');
    var wsBase = widget.getAttribute('data-chat-ws-base');
    var messagesBase = widget.getAttribute('data-chat-messages-base');
    var markReadBase = widget.getAttribute('data-chat-mark-read-base');
    var storageKey = widget.getAttribute('data-chat-storage-key') || 'support-chat';
    var authenticated = widget.getAttribute('data-chat-authenticated') === 'true';
    var defaultName = widget.getAttribute('data-chat-user-name') || '';
    var defaultEmail = widget.getAttribute('data-chat-user-email') || '';
    var conversation = safeJsonParse(localStorage.getItem(storageKey) || 'null', null) || null;
    var socket = null;
    var pendingMessages = [];
    var pollTimer = null;
    var socketHealthy = false;
    var openState = false;
    var unreadCount = 0;
    var backdrop = widget.querySelector('[data-chat-backdrop]');
    var currentAttachment = null;
    var currentAttachmentUrl = '';

    function isMobileChatMode() {
      return window.matchMedia && window.matchMedia('(max-width: 720px)').matches;
    }

    function setUnreadBanner(value) {
      if (!unreadBanner) return;
      var total = Math.max(0, Number(value) || 0);
      var showBanner = total > 0 && isMobileChatMode() && !openState;
      unreadBanner.hidden = !showBanner;
      if (showBanner) {
        unreadBanner.textContent = total === 1 ? '1 new message' : total + ' new messages';
      }
    }

    function persistConversation(data) {
      conversation = data;
      try {
        localStorage.setItem(storageKey, JSON.stringify(data));
      } catch (error) {}
      if (data && data.conversation) {
        unreadCount = Number(data.conversation.unread_client_count || 0);
        setBadge(badge, unreadCount);
        setUnreadBanner(unreadCount);
      }
    }

    function clearConversation() {
      conversation = null;
      try {
        localStorage.removeItem(storageKey);
      } catch (error) {}
      setBadge(badge, 0);
      setUnreadBanner(0);
    }

    function closeSocket() {
      if (socket) {
        try {
          socket.close();
        } catch (error) {}
      }
      socket = null;
      socketHealthy = false;
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function startPolling() {
      if (pollTimer || !openState) return;
      pollTimer = setInterval(function () {
        if (!openState || !conversation || !conversation.conversation) return;
        fetchConversationMessages();
      }, 5000);
    }

    function setSocketOffline() {
      socketHealthy = false;
      stopPolling();
      if (openState) {
        startPolling();
      }
    }

    function connectSocket(conversationId, token) {
      closeSocket();
      if (!conversationId) return;
      var url = wsBase + conversationId + '/' + (token ? '?token=' + encodeURIComponent(token) : '');
      socket = new WebSocket(wsUrl(url));
      socket.onopen = function () {
        socketHealthy = true;
        stopPolling();
        socket.send(JSON.stringify({ action: 'mark_read' }));
        while (pendingMessages.length) {
          socket.send(JSON.stringify(pendingMessages.shift()));
        }
        fetchConversationMessages();
      };
      socket.onmessage = function (event) {
        var data = safeJsonParse(event.data, {});
        if (data.type === 'message' && data.message) {
          appendMessage(thread, data.message);
          if (!openState && data.message.sender_role === 'admin') {
            unreadCount += 1;
            setBadge(badge, unreadCount);
            setUnreadBanner(unreadCount);
          } else if (openState) {
            unreadCount = 0;
            setBadge(badge, 0);
            setUnreadBanner(0);
          }
        }
        if (data.type === 'read.received') {
          unreadCount = 0;
          setBadge(badge, 0);
          setUnreadBanner(0);
        }
      };
      socket.onerror = function () {
        setSocketOffline();
      };
      socket.onclose = function () {
        socket = null;
        setSocketOffline();
      };
    }

    function conversationUrl(conversationId) {
      if (!conversationId) return '';
      return messagesBase + conversationId + '/messages/';
    }

    function renderAttachmentPreview(file) {
      if (!attachmentPreview) return;
      if (currentAttachmentUrl) {
        try {
          URL.revokeObjectURL(currentAttachmentUrl);
        } catch (error) {}
        currentAttachmentUrl = '';
      }
      if (!file) {
        attachmentPreview.hidden = true;
        attachmentPreview.innerHTML = '';
        return;
      }
      currentAttachmentUrl = URL.createObjectURL(file);
      attachmentPreview.hidden = false;
      attachmentPreview.innerHTML = '';
      var thumb = document.createElement('img');
      thumb.src = currentAttachmentUrl;
      thumb.alt = file.name || 'Attachment preview';
      var meta = document.createElement('div');
      meta.className = 'chat-attachment-meta';
      var title = document.createElement('strong');
      title.textContent = file.name || 'Selected image';
      var text = document.createElement('span');
      text.textContent = 'Ready to send';
      meta.appendChild(title);
      meta.appendChild(text);
      var clear = document.createElement('button');
      clear.type = 'button';
      clear.className = 'chat-attachment-clear';
      clear.setAttribute('aria-label', 'Remove attachment');
      clear.textContent = 'x';
      clear.addEventListener('click', function () {
        currentAttachment = null;
        if (attachmentInput) attachmentInput.value = '';
        renderAttachmentPreview(null);
      });
      attachmentPreview.appendChild(thumb);
      attachmentPreview.appendChild(meta);
      attachmentPreview.appendChild(clear);
    }

    function setAttachment(file) {
      currentAttachment = file || null;
      renderAttachmentPreview(currentAttachment);
    }

    function fetchConversationMessages() {
      if (!conversation || !conversation.conversation || !conversation.conversation.id) {
        return Promise.resolve();
      }
      var url = conversationUrl(conversation.conversation.id);
      var query = [];
      if (!authenticated && conversation.conversation.token) {
        query.push('token=' + encodeURIComponent(conversation.conversation.token));
      }
      if (query.length) {
        url += (url.indexOf('?') === -1 ? '?' : '&') + query.join('&');
      }
      return fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).then(function (response) {
        return response.json();
      }).then(function (data) {
        if (!data.ok) return;
        loadConversation(data, false);
      });
    }

    function postMessageViaHttp(content, attachment) {
      if (!conversation || !conversation.conversation || !conversation.conversation.id) {
        return Promise.resolve();
      }
      var payload = new FormData();
      payload.set('content', content || '');
      if (conversation.conversation.token) {
        payload.set('token', conversation.conversation.token);
      }
      if (attachment) {
        payload.set('attachment', attachment);
      }
      return fetch(conversationUrl(conversation.conversation.id), {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfInput ? csrfInput.value : getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: payload
      }).then(function (response) {
        return response.json();
      }).then(function (data) {
        if (!data.ok) return;
        if (!socketHealthy) {
          fetchConversationMessages();
        }
      });
    }

    function loadConversation(data, shouldConnect) {
      if (!data || !data.conversation) return;
      persistConversation(data);
      renderMessages(thread, data.messages || [], 'client');
      unreadCount = Number(data.conversation.unread_client_count || 0);
      if (subtitle) {
        subtitle.textContent = data.conversation.display_name ? ('Conversation with ' + data.conversation.display_name) : 'Send a message and our team will reply here.';
      }
      if (prechat) {
        prechat.style.display = authenticated ? 'none' : '';
      }
      if (shouldConnect !== false) {
        connectSocket(data.conversation.id, data.conversation.token);
      } else {
        socketHealthy = false;
      }
      if (shouldConnect !== false) {
        openState = true;
      }
      setBadge(badge, openState ? 0 : unreadCount);
      if (input && openState) input.focus();
    }

    function startConversation() {
      var payload = new URLSearchParams();
      var token = conversation && conversation.conversation ? conversation.conversation.token : '';
      if (token) payload.set('token', token);
      if (!authenticated) {
        payload.set('guest_name', (nameInput && nameInput.value || '').trim());
        payload.set('guest_email', (emailInput && emailInput.value || '').trim());
      } else {
        payload.set('guest_name', defaultName);
        payload.set('guest_email', defaultEmail);
      }
      return fetch(startUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          'X-CSRFToken': csrfInput ? csrfInput.value : getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: payload.toString()
      }).then(function (response) {
        return response.json();
      });
    }

    function ensureConversationAndSend(message, attachmentFile, forceHttp) {
      if (conversation && conversation.conversation && conversation.conversation.id) {
        if (attachmentFile || forceHttp) {
          postMessageViaHttp(message, attachmentFile);
          return;
        }
        var payload = { action: 'message', content: message };
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(payload));
        } else {
          postMessageViaHttp(message, attachmentFile);
        }
        return;
      }
      startConversation().then(function (data) {
        if (!data.ok) return;
        loadConversation(data);
        if (attachmentFile || forceHttp) {
          postMessageViaHttp(message, attachmentFile);
          return;
        }
        var payload = { action: 'message', content: message };
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(payload));
        } else {
          postMessageViaHttp(message, attachmentFile);
        }
      });
    }

    function openPanel() {
      openState = true;
      if (panel) {
        panel.hidden = false;
        panel.classList.add('is-open');
      }
      widget.classList.add('is-open');
      if (!isMobileChatMode()) {
        document.body.classList.add('chat-modal-open');
      }
      if (backdrop) backdrop.hidden = false;
      if (conversation && conversation.conversation) {
        unreadCount = 0;
        setBadge(badge, 0);
        setUnreadBanner(0);
        if (!socket) {
          connectSocket(conversation.conversation.id, conversation.conversation.token);
          if (!socketHealthy) {
            startPolling();
          }
        }
        fetchConversationMessages();
      } else if (!authenticated && prechat) {
        prechat.style.display = '';
      }
      if (!conversation && authenticated && !socket) {
        startConversation().then(function (data) {
          if (data.ok) loadConversation(data);
        });
      }
      if (!socketHealthy) {
        startPolling();
      }
    }

    function closePanel() {
      openState = false;
      if (panel) {
        panel.classList.remove('is-open');
        panel.hidden = true;
      }
      widget.classList.remove('is-open');
      document.body.classList.remove('chat-modal-open');
      if (backdrop) backdrop.hidden = true;
      setUnreadBanner(unreadCount);
      stopPolling();
    }

    toggleButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        if (panel && !panel.hidden) closePanel();
        else openPanel();
      });
    });

    document.addEventListener('click', function (event) {
      if (!openState || !panel || panel.hidden) return;
      if (widget.contains(event.target)) return;
      closePanel();
    });

    if (composeForm) {
      composeForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var message = (input && input.value || '').trim();
        if (!message && !currentAttachment) return;
        if (!authenticated && (!nameInput || !nameInput.value.trim()) && (!emailInput || !emailInput.value.trim())) {
          if (subtitle) subtitle.textContent = 'Please add your name or email before sending a message.';
          return;
        }
        input.value = '';
        if (currentAttachment) {
          ensureConversationAndSend(message, currentAttachment, true);
          currentAttachment = null;
          renderAttachmentPreview(null);
        } else {
          ensureConversationAndSend(message);
        }
        if (panel) panel.hidden = false;
      });
    }

    if (attachButton && attachmentInput) {
      attachButton.addEventListener('click', function () {
        attachmentInput.removeAttribute('capture');
        attachmentInput.click();
      });
    }

    if (attachmentInput) {
      attachmentInput.addEventListener('change', function () {
        setAttachment(attachmentInput.files && attachmentInput.files[0] ? attachmentInput.files[0] : null);
      });
    }

    if (input) {
      bindAutosizeTextarea(input, isMobileChatMode() ? 132 : 160);
      input.addEventListener('keydown', function (event) {
        if ((event.key === 'Enter' && !event.shiftKey) && !event.isComposing) {
          event.preventDefault();
          composeForm.requestSubmit ? composeForm.requestSubmit() : composeForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
      });
    }

    if (conversation && conversation.conversation && conversation.messages) {
      loadConversation(conversation, false);
    } else {
      setBadge(badge, 0);
      setUnreadBanner(0);
    }

    if (openState && !socketHealthy) {
      startPolling();
    }
  }

  function initInbox(inbox) {
    var thread = inbox.querySelector('[data-chat-thread]');
    var composeForm = inbox.querySelector('[data-chat-compose]');
    var input = inbox.querySelector('[data-chat-input]');
    var attachmentInput = inbox.querySelector('[data-chat-attachment]');
    var attachButton = inbox.querySelector('[data-chat-attach]');
    var attachmentPreview = inbox.querySelector('[data-chat-attachment-preview]');
    var conversationList = inbox.querySelectorAll('[data-chat-select]');
    var selectedMessagesNode = inbox.querySelector('[data-chat-selected-messages]');
    var selectedMessages = safeJsonParse(selectedMessagesNode ? selectedMessagesNode.textContent : '[]', []);
    var currentConversationId = inbox.getAttribute('data-selected-conversation-id') || '';
    var currentConversationToken = inbox.getAttribute('data-selected-conversation-token') || '';
    var wsBase = inbox.getAttribute('data-chat-ws-base');
    var messagesBase = inbox.getAttribute('data-chat-messages-base');
    var selectedTitle = inbox.querySelector('[data-chat-thread-title]');
    var selectedSubtitle = inbox.querySelector('[data-chat-thread-subtitle]');
    var selectedStatus = inbox.querySelector('[data-chat-thread-status]');
    var socket = null;
    var pendingMessages = [];
    var pollTimer = null;
    var currentAttachment = null;
    var currentAttachmentUrl = '';

    function renderAttachmentPreview(file) {
      if (!attachmentPreview) return;
      if (currentAttachmentUrl) {
        try {
          URL.revokeObjectURL(currentAttachmentUrl);
        } catch (error) {}
        currentAttachmentUrl = '';
      }
      if (!file) {
        attachmentPreview.hidden = true;
        attachmentPreview.innerHTML = '';
        return;
      }
      currentAttachmentUrl = URL.createObjectURL(file);
      attachmentPreview.hidden = false;
      attachmentPreview.innerHTML = '';
      var thumb = document.createElement('img');
      thumb.src = currentAttachmentUrl;
      thumb.alt = file.name || 'Attachment preview';
      var meta = document.createElement('div');
      meta.className = 'chat-attachment-meta';
      var title = document.createElement('strong');
      title.textContent = file.name || 'Selected image';
      var text = document.createElement('span');
      text.textContent = 'Ready to reply';
      meta.appendChild(title);
      meta.appendChild(text);
      var clear = document.createElement('button');
      clear.type = 'button';
      clear.className = 'chat-attachment-clear';
      clear.setAttribute('aria-label', 'Remove attachment');
      clear.textContent = 'x';
      clear.addEventListener('click', function () {
        currentAttachment = null;
        if (attachmentInput) attachmentInput.value = '';
        renderAttachmentPreview(null);
      });
      attachmentPreview.appendChild(thumb);
      attachmentPreview.appendChild(meta);
      attachmentPreview.appendChild(clear);
    }

    function setAttachment(file) {
      currentAttachment = file || null;
      renderAttachmentPreview(currentAttachment);
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function startPolling() {
      if (pollTimer || !currentConversationId) return;
      pollTimer = setInterval(function () {
        if (!currentConversationId) return;
        fetchConversation(currentConversationId, currentConversationToken);
      }, 5000);
    }

    function updateListBadge(conversationId, unreadCount) {
      var item = inbox.querySelector('[data-chat-select][data-conversation-id="' + conversationId + '"]');
      if (!item) return;
      var badge = item.querySelector('.badge');
      if (!badge) return;
      if (unreadCount > 0) {
        badge.textContent = String(unreadCount);
        badge.className = 'badge danger';
      } else if (item.dataset.status === 'closed') {
        badge.textContent = 'Closed';
        badge.className = 'badge';
      } else {
        badge.textContent = 'Open';
        badge.className = 'badge success';
      }
    }

    function closeSocket() {
      if (socket) {
        try {
          socket.close();
        } catch (error) {}
      }
      socket = null;
    }

    function connectSocket(conversationId, token) {
      closeSocket();
      stopPolling();
      if (!conversationId) return;
      var url = wsBase + conversationId + '/' + (token ? '?token=' + encodeURIComponent(token) : '');
      socket = new WebSocket(wsUrl(url));
      socket.onopen = function () {
        socket.send(JSON.stringify({ action: 'mark_read' }));
        while (pendingMessages.length) {
          socket.send(JSON.stringify(pendingMessages.shift()));
        }
        fetchConversation(conversationId, token);
      };
      socket.onmessage = function (event) {
        var data = safeJsonParse(event.data, {});
        if (data.type === 'message' && data.message) {
          if (data.conversation_id === currentConversationId) {
            appendMessage(thread, data.message);
          } else if (data.message.sender_role === 'client') {
            var item = inbox.querySelector('[data-chat-select][data-conversation-id="' + data.conversation_id + '"]');
            if (item) {
              var badge = item.querySelector('.badge');
              var nextCount = badge && badge.classList.contains('danger') ? Number(badge.textContent || '0') + 1 : 1;
              updateListBadge(data.conversation_id, nextCount);
            }
          }
        }
        if (data.type === 'read.received' && data.conversation_id === currentConversationId) {
          updateListBadge(currentConversationId, 0);
        }
      };
      socket.onerror = function () {
        startPolling();
      };
      socket.onclose = function () {
        socket = null;
        startPolling();
      };
    }

    function postMessageViaHttp(content) {
      if (!currentConversationId) return Promise.resolve();
      var payload = new FormData();
      payload.set('content', content || '');
      if (currentConversationToken) {
        payload.set('token', currentConversationToken);
      }
      if (currentAttachment) {
        payload.set('attachment', currentAttachment);
      }
      return fetch(messagesBase + currentConversationId + '/messages/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: payload
      }).then(function (response) {
        return response.json();
      }).then(function (data) {
        if (data && data.ok) {
          if (!socket || socket.readyState !== WebSocket.OPEN) {
            return fetchConversation(currentConversationId, currentConversationToken);
          }
        }
      });
    }

    function loadConversation(data, shouldConnect) {
      if (!data || !data.conversation) return;
      currentConversationId = data.conversation.id;
      currentConversationToken = data.conversation.token || '';
      renderMessages(thread, data.messages || [], 'admin');
      if (selectedTitle) selectedTitle.textContent = data.conversation.display_name || 'Support conversation';
      if (selectedSubtitle) {
        var subtitleParts = [];
        if (data.conversation.subject) subtitleParts.push(data.conversation.subject);
        if (data.conversation.contact_label) subtitleParts.push(data.conversation.contact_label);
        selectedSubtitle.textContent = subtitleParts.length ? subtitleParts.join(' | ') : (data.conversation.contact_label || '');
      }
      if (selectedStatus) selectedStatus.textContent = data.conversation.status || 'Open';
      if (shouldConnect !== false) {
        connectSocket(currentConversationId, currentConversationToken);
      }
      if (input) input.focus();
    }

    function fetchConversation(conversationId, token) {
      if (!conversationId) return Promise.resolve();
      var url = messagesBase + conversationId + '/messages/';
      return fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).then(function (response) {
        return response.json();
      }).then(function (data) {
        if (data.ok) {
          loadConversation(data, false);
          var item = inbox.querySelector('[data-chat-select][data-conversation-id="' + conversationId + '"]');
          if (item) {
            updateListBadge(conversationId, 0);
            inbox.querySelectorAll('[data-chat-select]').forEach(function (node) {
              node.classList.toggle('active', node === item);
            });
          }
        }
      });
    }

    conversationList.forEach(function (item) {
      item.addEventListener('click', function () {
        var conversationId = item.getAttribute('data-conversation-id');
        fetchConversation(conversationId, item.getAttribute('data-conversation-token'));
      });
    });

    if (composeForm) {
      composeForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var message = (input && input.value || '').trim();
        if ((!message && !currentAttachment) || !currentConversationId) return;
        input.value = '';
        if (currentAttachment) {
          postMessageViaHttp(message);
          currentAttachment = null;
          renderAttachmentPreview(null);
          return;
        }
        var payload = { action: 'message', content: message };
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(payload));
        } else {
          postMessageViaHttp(message);
          if (!socket) {
            connectSocket(currentConversationId, currentConversationToken);
          }
        }
      });
    }

    if (attachButton && attachmentInput) {
      attachButton.addEventListener('click', function () {
        attachmentInput.removeAttribute('capture');
        attachmentInput.click();
      });
    }

    if (attachmentInput) {
      attachmentInput.addEventListener('change', function () {
        setAttachment(attachmentInput.files && attachmentInput.files[0] ? attachmentInput.files[0] : null);
      });
    }

    if (selectedMessages && selectedMessages.length) {
      renderMessages(thread, selectedMessages, 'admin');
    } else if (!currentConversationId) {
      renderMessages(thread, [], 'admin');
    }

    if (currentConversationId) {
      connectSocket(currentConversationId, currentConversationToken);
      startPolling();
    }
  }

  document.querySelectorAll('[data-chat-widget]').forEach(initWidget);
  document.querySelectorAll('[data-chat-inbox]').forEach(initInbox);
})();


