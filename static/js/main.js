// static/js/main.js v7 - FINAL VERSION
// Enhanced Chat Manager with Sidebar Integration and Image Upload

(() => {
  // DOM Elements
  const chatsListEl = document.getElementById('chats-list');
  const chatsLoadingEl = document.getElementById('chats-loading');
  const newChatBtn = document.getElementById('new-chat-btn');
  const chatMessagesEl = document.getElementById('chat-messages');
  const chatTitleEl = document.getElementById('chat-title');
  const initialMessageEl = document.getElementById('initial-message');
  
  // State
  let currentChatId = null;
  let conversations = [];
  let isProcessing = false;
  let pendingImage = null;  // Store pending image data for wound analyzer

  // --- CSRF TOKEN ---
  function getCSRFToken() {
    const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  }
  const csrftoken = getCSRFToken();

  // --- API FUNCTIONS ---
  async function fetchConversations() {
    try {
      const res = await fetch('/chat/api/conversations/');
      const data = await res.json();
      return data.conversations || [];
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
      showNotification('Failed to load conversations', 'error');
      return [];
    }
  }

  async function createConversation(title = 'New conversation', metadata = {}) {
    try {
      const res = await fetch('/chat/api/conversations/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ title, metadata })
      });
      const data = await res.json();
      return data.success ? data.conversation : null;
    } catch (err) {
      console.error("Failed to create conversation:", err);
      showNotification('Failed to create conversation', 'error');
      return null;
    }
  }

  async function fetchMessages(conversationId) {
    try {
      const res = await fetch(`/chat/api/conversations/${conversationId}/messages/`);
      const data = await res.json();
      return data.messages || [];
    } catch (err) {
      console.error("Failed to fetch messages:", err);
      return [];
    }
  }

  async function addMessage(conversationId, content, role = 'user', locationData = null, imageData = null) {
    try {
      const payload = { role, content };
      
      if (locationData) {
        payload.latitude = locationData.latitude;
        payload.longitude = locationData.longitude;
      }
      
      // Add image data if provided
      if (imageData) {
        payload.image = imageData;
      }
      
      const res = await fetch(`/chat/api/conversations/${conversationId}/messages/add/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      return data.success ? data : null;
    } catch (err) {
      console.error("Failed to add message:", err);
      return null;
    }
  }

  // --- UI FUNCTIONS ---
  function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg z-50 transform translate-x-full transition-transform duration-300 ${type === 'error' ? 'bg-red-100 border border-red-400 text-red-700' : 'bg-green-100 border border-green-400 text-green-700'}`;
    notification.innerHTML = `
      <div class="flex items-center">
        <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'} mr-2"></i>
        <span>${message}</span>
      </div>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.style.transform = 'translateX(0)', 10);
    setTimeout(() => {
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // --- SIDEBAR MANAGEMENT ---
  async function loadAndRenderSidebar() {
    if (!chatsListEl) return;
    
    conversations = await fetchConversations();
    
    // Hide loading
    if (chatsLoadingEl) {
      chatsLoadingEl.style.opacity = '0';
      setTimeout(() => chatsLoadingEl.remove(), 300);
    }
    
    // Clear and render
    chatsListEl.innerHTML = '<h3 class="text-sm font-semibold text-gray-500 mb-3 px-2">Recent Conversations</h3>';
    
    if (conversations.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'text-sm text-gray-500 p-4 text-center';
      empty.textContent = 'No conversations yet. Start a new chat!';
      chatsListEl.appendChild(empty);
      return;
    }
    
    // Sort: pinned first, then by date
    const sorted = [...conversations].sort((a, b) => {
      if (a.is_pinned && !b.is_pinned) return -1;
      if (!a.is_pinned && b.is_pinned) return 1;
      return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
    });
    
    sorted.forEach((conv, index) => {
      const item = createConversationItem(conv);
      chatsListEl.appendChild(item);
      
      // Staggered animation
      item.style.animationDelay = `${index * 0.05}s`;
      item.classList.add('conversation-item-enter');
    });
  }

  function createConversationItem(conv) {
    const item = document.createElement('div');
    item.className = `conversation-item group/item relative p-3 rounded-lg cursor-pointer hover:bg-gray-100 flex justify-between items-center transition-all duration-200 ${conv.id === currentChatId ? 'active bg-medical-primary/10' : ''}`;
    item.dataset.chatId = conv.id;
    
    // Content
    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1 overflow-hidden min-w-0 mr-2';
    
    const titleDiv = document.createElement('div');
    titleDiv.className = 'font-medium truncate flex items-center gap-1.5 text-sm text-gray-800';
    
    if (conv.is_pinned) {
      const pinIcon = document.createElement('span');
      pinIcon.className = 'text-medical-primary flex-shrink-0';
      pinIcon.innerHTML = '<i class="fas fa-thumbtack text-xs"></i>';
      titleDiv.appendChild(pinIcon);
    }
    
    const titleText = document.createElement('span');
    titleText.className = 'truncate';
    titleText.textContent = conv.title;
    titleDiv.appendChild(titleText);
    
    const previewDiv = document.createElement('div');
    previewDiv.className = 'text-xs text-gray-500 mt-1 truncate';
    previewDiv.textContent = conv.preview || 'No messages yet';
    
    contentDiv.appendChild(titleDiv);
    contentDiv.appendChild(previewDiv);
    
    // Menu button
    const menuBtn = document.createElement('button');
    menuBtn.className = 'p-1.5 text-gray-400 hover:text-gray-700 opacity-0 group-hover/item:opacity-100 transition-all duration-200 rounded hover:bg-gray-200';
    menuBtn.innerHTML = '<i class="fas fa-ellipsis-v text-xs"></i>';
    menuBtn.onclick = (e) => {
      e.stopPropagation();
      showConversationMenu(e, conv);
    };
    
    item.appendChild(contentDiv);
    item.appendChild(menuBtn);
    
    // Click handler
    item.addEventListener('click', () => {
      switchChat(conv.id);
    });
    
    return item;
  }

  function showConversationMenu(event, conv) {
    // Remove any existing menus
    document.querySelectorAll('.conversation-menu').forEach(el => el.remove());
    
    const menu = document.createElement('div');
    menu.className = 'conversation-menu absolute bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-1 min-w-[120px]';
    menu.style.left = `${event.clientX - 100}px`;
    menu.style.top = `${event.clientY + 10}px`;
    
    const menuItems = [
      { label: conv.is_pinned ? 'Unpin' : 'Pin', icon: 'thumbtack', action: () => togglePin(conv) },
      { label: 'Rename', icon: 'edit', action: () => renameConversation(conv) },
      { label: 'Delete', icon: 'trash', action: () => deleteConversation(conv), destructive: true }
    ];
    
    menuItems.forEach(item => {
      const btn = document.createElement('button');
      btn.className = `w-full text-left px-3 py-2 text-sm flex items-center gap-2 hover:bg-gray-100 ${item.destructive ? 'text-red-600' : 'text-gray-700'}`;
      btn.innerHTML = `<i class="fas fa-${item.icon} text-xs"></i><span>${item.label}</span>`;
      btn.onclick = (e) => {
        e.stopPropagation();
        item.action();
        menu.remove();
      };
      menu.appendChild(btn);
    });
    
    document.body.appendChild(menu);
    
    // Close menu on outside click
    setTimeout(() => {
      const closeMenu = (e) => {
        if (!menu.contains(e.target)) {
          menu.remove();
          document.removeEventListener('click', closeMenu);
        }
      };
      document.addEventListener('click', closeMenu);
    }, 10);
  }

  async function togglePin(conv) {
    try {
      const res = await fetch(`/chat/api/conversations/${conv.id}/update/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ is_pinned: !conv.is_pinned })
      });
      
      if (res.ok) {
        await loadAndRenderSidebar();
        showNotification(conv.is_pinned ? 'Unpinned conversation' : 'Pinned conversation');
      }
    } catch (err) {
      console.error('Error toggling pin:', err);
    }
  }

  async function renameConversation(conv) {
    const newTitle = prompt('Enter new conversation title:', conv.title);
    if (newTitle && newTitle !== conv.title) {
      try {
        const res = await fetch(`/chat/api/conversations/${conv.id}/update/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
          },
          body: JSON.stringify({ title: newTitle })
        });
        
        if (res.ok) {
          await loadAndRenderSidebar();
          if (currentChatId === conv.id && chatTitleEl) {
            chatTitleEl.textContent = newTitle;
          }
          showNotification('Conversation renamed');
        }
      } catch (err) {
        console.error('Error renaming conversation:', err);
      }
    }
  }

  async function deleteConversation(conv) {
    if (confirm(`Delete "${conv.title}"? This action cannot be undone.`)) {
      try {
        const res = await fetch(`/chat/api/conversations/${conv.id}/delete/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrftoken }
        });
        
        if (res.ok) {
          // If deleting active chat, switch to welcome screen
          if (currentChatId === conv.id) {
            currentChatId = null;
            if (window.uiManager) {
              window.uiManager.switchToWelcomeScreen();
            }
          }
          
          await loadAndRenderSidebar();
          showNotification('Conversation deleted');
        }
      } catch (err) {
        console.error('Error deleting conversation:', err);
      }
    }
  }

  // --- CHAT MANAGEMENT ---
  async function switchChat(chatId) {
    if (isProcessing || currentChatId === chatId) return;
    
    isProcessing = true;
    currentChatId = chatId;
    
    // Update URL
    updateUrlWithChatId(chatId);
    
    // Update active state in sidebar
    updateSidebarActiveState(chatId);
    
    // Switch to chat interface if needed
    if (window.uiManager && !document.getElementById('chatInterface').classList.contains('hidden')) {
      await loadChatMessages(chatId);
    } else if (window.uiManager) {
      window.uiManager.switchToChatInterface(chatId);
    }
    
    isProcessing = false;
  }

  function updateUrlWithChatId(chatId) {
    const url = new URL(window.location);
    url.searchParams.set('chat', chatId);
    window.history.replaceState({}, '', url);
  }

  function updateSidebarActiveState(chatId) {
    if (!chatsListEl) return;
    
    document.querySelectorAll('.conversation-item').forEach(item => {
      const itemChatId = parseInt(item.dataset.chatId);
      if (itemChatId === chatId) {
        item.classList.add('active', 'bg-medical-primary/10');
      } else {
        item.classList.remove('active', 'bg-medical-primary/10');
      }
    });
  }

  async function loadChatMessages(chatId) {
    if (!chatMessagesEl) return;
    
    // Show loading state
    chatMessagesEl.innerHTML = `
      <div class="flex items-center justify-center py-12">
        <div class="flex flex-col items-center">
          <div class="flex space-x-2 mb-2">
            <div class="w-2 h-2 bg-medical-primary rounded-full animate-pulse"></div>
            <div class="w-2 h-2 bg-medical-primary rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
            <div class="w-2 h-2 bg-medical-primary rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
          </div>
          <span class="text-xs text-gray-500">Loading messages...</span>
        </div>
      </div>
    `;
    
    const messages = await fetchMessages(chatId);
    renderChatMessages(messages);
    
    // Update chat title
    const conversation = conversations.find(c => c.id === chatId);
    if (conversation && chatTitleEl) {
      chatTitleEl.textContent = conversation.title;
    }
  }

  function renderChatMessages(messages) {
    if (!chatMessagesEl) return;
    
    chatMessagesEl.innerHTML = '';
    
    if (messages.length === 0) {
      const welcomeMsg = document.createElement('div');
      welcomeMsg.className = 'text-center py-12 text-gray-500';
      welcomeMsg.innerHTML = `
        <div class="mb-4">
          <img src="{% static 'img/logo.png' %}" alt="Sahatek Logo" class="h-16 w-16 mx-auto">
        </div>
        <h3 class="text-lg font-semibold mb-2">Hello! I'm Sahatek</h3>
        <p class="text-sm">Your AI health assistant. How can I help you today?</p>
      `;
      chatMessagesEl.appendChild(welcomeMsg);
      return;
    }
    
    messages.forEach(msg => {
      appendMessage(msg.role, msg.content, msg.metadata);
    });
    
    scrollToBottom();
  }

  function appendMessage(role, content, metadata = null, imageData = null) {
    if (!chatMessagesEl) return;
    
    const msgDiv = document.createElement('div');
    msgDiv.className = `flex w-full mb-4 ${role === 'user' ? 'justify-end' : 'justify-start'} message-enter`;
    
    const bubble = document.createElement('div');
    bubble.className = `max-w-[80%] p-4 rounded-2xl ${role === 'user' ? 'bg-medical-primary text-white rounded-br-none' : 'bg-white border border-gray-200 text-medical-neutral rounded-bl-none shadow-sm'}`;
    
    // Create content container
    const contentDiv = document.createElement('div');
    contentDiv.className = 'text-sm whitespace-pre-wrap';
    contentDiv.textContent = content;
    
    bubble.appendChild(contentDiv);
    
    // Add image preview if available
    if (metadata && metadata.image) {
      const imgDiv = document.createElement('div');
      imgDiv.className = 'mt-3 mb-2';
      const img = document.createElement('img');
      img.src = metadata.image;
      img.className = 'max-w-full h-auto rounded-lg border border-gray-200';
      img.alt = 'Uploaded image';
      imgDiv.appendChild(img);
      bubble.appendChild(imgDiv);
    } else if (imageData) {
      // For new messages with images
      const imgDiv = document.createElement('div');
      imgDiv.className = 'mt-3 mb-2';
      const img = document.createElement('img');
      img.src = imageData;
      img.className = 'max-w-full h-auto rounded-lg border border-gray-200';
      img.alt = 'Uploaded image';
      imgDiv.appendChild(img);
      bubble.appendChild(imgDiv);
    }
    
    msgDiv.appendChild(bubble);
    chatMessagesEl.appendChild(msgDiv);
    
    scrollToBottom();
  }

  function scrollToBottom() {
    if (chatMessagesEl) {
      chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }
  }

  // --- MESSAGE SENDING ---
  async function sendMessage(content, imageData = null) {
    if (!content.trim() || isProcessing) return;
    
    // Use pending image if no image is provided
    if (!imageData && pendingImage) {
      imageData = pendingImage;
      pendingImage = null;
    }
    
    if (!currentChatId) {
      // Create new conversation
      const conv = await createConversation(content.substring(0, 30));
      if (!conv) return;
      
      currentChatId = conv.id;
      await loadAndRenderSidebar();
      updateUrlWithChatId(conv.id);
    }
    
    // Add user message
    appendMessage('user', content, null, imageData);
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to server (with optional image)
    const result = await addMessage(currentChatId, content, 'user', null, imageData);
    
    // Remove typing indicator and add bot response
    removeTypingIndicator();
    
    if (result && result.bot_message) {
      setTimeout(() => {
        appendMessage('assistant', result.bot_message.content, result.bot_message.metadata);
      }, 500);
    } else {
      setTimeout(() => {
        appendMessage('assistant', "I've received your message. How can I assist you further?");
      }, 1000);
    }
    
    // Refresh sidebar preview
    setTimeout(() => loadAndRenderSidebar(), 1000);
  }

  function showTypingIndicator() {
    if (!chatMessagesEl) return;
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'flex w-full mb-4 justify-start';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = `
      <div class="flex items-end space-x-3">
        <img src="{% static 'img/logo.png' %}" alt="Sahatek Logo" class="h-10 w-10">
        <div class="bg-white border border-gray-200 rounded-2xl rounded-bl-none px-5 py-3">
          <div class="flex items-center space-x-1">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
      </div>
    `;
    chatMessagesEl.appendChild(typingDiv);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const typingDiv = document.getElementById('typing-indicator');
    if (typingDiv) typingDiv.remove();
  }

  // --- AGENT CHAT CREATION ---
  async function createAgentChat(agentName) {
    const title = getAgentTitle(agentName);
    const metadata = { agent: agentName };
    
    const conv = await createConversation(title, metadata);
    if (conv) {
      await loadAndRenderSidebar();
      
      // Send agent-specific welcome message
      setTimeout(async () => {
        const welcomeMessage = getAgentWelcomeMessage(agentName);
        await addMessage(conv.id, welcomeMessage, 'assistant');
        
        // Reload messages to show welcome
        if (currentChatId === conv.id) {
          await loadChatMessages(conv.id);
        }
      }, 500);
      
      return conv.id;
    }
    return null;
  }

  function getAgentTitle(agentName) {
    const titles = {
      'mental-health': 'Mental Health Support',
      'general-info': 'Medical Information',
      'symptoms-checker': 'Symptoms Checker',
      'orientation': 'Medical Guidance',
      'rumor-check': 'Health Fact Check',
      'computer-vision': 'Wound Analyzer'
    };
    return titles[agentName] || 'Specialized Chat';
  }

  function getAgentWelcomeMessage(agentName) {
    const messages = {
      'mental-health': "Hello! I'm your mental health assistant. I'm here to provide emotional support and coping strategies. How are you feeling today?",
      'general-info': "Hello! I'm your medical information assistant. I can provide evidence-based information about health conditions, medications, and treatments. What would you like to know?",
      'symptoms-checker': "Hello! I'm your symptoms checker. Please describe your symptoms in detail, and I'll help you understand possible causes and when to seek medical attention.",
      'orientation': "Hello! I'm your medical guidance assistant. I provide step-by-step instructions for medical procedures and first aid. How can I guide you today?",
      'rumor-check': "Hello! I'm your health fact checker. I can verify medical claims and provide evidence-based information. What health claim would you like me to check?",
      'computer-vision': "Hello! I'm your wound analysis assistant. You can upload images of wounds, rashes, or skin conditions for analysis. Click the upload button or drag and drop an image."
    };
    return messages[agentName] || "Hello! I'm your specialized health assistant. How can I help you today?";
  }

  // --- EVENT LISTENERS ---
  function initEventListeners() {
    // New Chat Button
    if (newChatBtn) {
      newChatBtn.addEventListener('click', async () => {
        newChatBtn.style.transform = 'scale(0.95)';
        setTimeout(async () => {
          newChatBtn.style.transform = '';
          const conv = await createConversation();
          if (conv) {
            await loadAndRenderSidebar();
            switchChat(conv.id);
            showNotification('New conversation started');
          }
        }, 200);
      });
    }
    
    // Send buttons
    const sendBtn = document.getElementById('send-btn');
    const sendChatBtn = document.getElementById('sendChatBtn');
    const chatInput = document.getElementById('chat-input');
    const chatInputChat = document.getElementById('chatInput');
    
    function handleSend() {
      // Get the correct input based on which interface is visible
      const chatInterface = document.getElementById('chatInterface');
      const input = chatInterface && !chatInterface.classList.contains('hidden') ? chatInputChat : chatInput;
      const content = input?.value.trim();
      if (content) {
        sendMessage(content);
        input.value = '';
        if (input.style.height !== 'auto') {
          input.style.height = 'auto';
        }
      }
    }
    
    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (sendChatBtn) sendChatBtn.addEventListener('click', handleSend);
    
    // File upload for wound analyzer chat
    try {
      const fileInput = document.getElementById('fileInput');
      const uploadBtnChat = document.getElementById('upload-btn-chat');
      
      console.log('🔍 Looking for upload elements:', { fileInput: !!fileInput, uploadBtnChat: !!uploadBtnChat });
      
      if (uploadBtnChat && fileInput) {
        console.log('✅ Upload button and file input found, setting up handlers');
        
        uploadBtnChat.onclick = function(e) {
          console.log('📁 Upload button clicked');
          e.preventDefault();
          e.stopPropagation();
          fileInput.click();
          return false;
        };
        
        fileInput.onchange = function(e) {
          console.log('📂 File changed event fired');
          const file = this.files[0];
          console.log('📂 File selected:', file?.name, file?.type);
          
          if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(event) {
              pendingImage = event.target.result;
              console.log('✅ Image loaded:', pendingImage.substring(0, 50) + '...');
              showNotification('Image attached. Type a message and send!', 'info');
              
              // Display image preview in input area
              const previewContainer = document.getElementById('image-preview-container');
              if (previewContainer) {
                previewContainer.innerHTML = `
                  <div class="flex items-center justify-between bg-gray-50 p-2 rounded-lg">
                    <div class="flex items-center">
                      <img src="${pendingImage}" alt="Preview" class="w-10 h-10 object-cover rounded mr-2">
                      <span class="text-sm text-gray-600">Image attached</span>
                    </div>
                    <button id="remove-image-btn" class="text-red-500 hover:text-red-700">
                      <i class="fas fa-times"></i>
                    </button>
                  </div>
                `;
                
                // Add remove image handler
                document.getElementById('remove-image-btn').addEventListener('click', function() {
                  pendingImage = null;
                  fileInput.value = '';
                  previewContainer.innerHTML = '';
                  showNotification('Image removed', 'info');
                });
              }
            };
            reader.onerror = function() {
              console.error('❌ Error reading file');
              showNotification('Error reading image file', 'error');
            };
            reader.readAsDataURL(file);
          } else {
            console.warn('⚠️ Not an image:', file?.type);
            showNotification('Please select an image file', 'error');
          }
        };
      } else {
        console.warn('⚠️ Upload elements not found - fileInput:', !!fileInput, 'uploadBtnChat:', !!uploadBtnChat);
      }
    } catch(err) {
      console.error('❌ Error setting up upload handler:', err);
    }
    
    // Enter key handling
    if (chatInput) {
      chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleSend();
        }
      });
    }
    
    if (chatInputChat) {
      chatInputChat.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleSend();
        }
      });
    }
    
    // Clear chat button
    const clearChatBtn = document.getElementById('clearChatBtn');
    if (clearChatBtn) {
      clearChatBtn.addEventListener('click', () => {
        if (confirm('Clear all messages in this conversation?')) {
          if (chatMessagesEl) {
            chatMessagesEl.innerHTML = '';
            const welcomeMsg = document.createElement('div');
            welcomeMsg.className = 'text-center py-12 text-gray-500';
            welcomeMsg.innerHTML = `
              <div class="mb-4">
                <img src="{% static 'img/logo.png' %}" alt="Sahatek Logo" class="h-16 w-16 mx-auto">
              </div>
              <h3 class="text-lg font-semibold mb-2">Conversation cleared</h3>
              <p class="text-sm">Start a new message</p>
            `;
            chatMessagesEl.appendChild(welcomeMsg);
          }
        }
      });
    }
    
    // Clear pending image when switching chats
    document.addEventListener('chatSwitched', () => {
      pendingImage = null;
      const previewContainer = document.getElementById('image-preview-container');
      if (previewContainer) previewContainer.innerHTML = '';
    });
  }

  // --- INITIALIZATION ---
  function init() {
    console.log('Chat Manager initialized');
    
    // Load sidebar conversations
    setTimeout(() => loadAndRenderSidebar(), 300);
    
    // Set up event listeners
    initEventListeners();
    
    // Double-check upload handler (fallback)
    setTimeout(() => {
      const uploadBtnChat = document.getElementById('upload-btn-chat');
      const fileInput = document.getElementById('fileInput');
      if (uploadBtnChat && fileInput && !uploadBtnChat.onclick) {
        console.log('🔧 Setting up upload handler fallback');
        uploadBtnChat.onclick = function(e) {
          console.log('📁 Upload button clicked (fallback)');
          e.preventDefault();
          fileInput.click();
          return false;
        };
      }
    }, 500);
    
    // Expose public API
    window.chatManager = {
      loadChatFromUrl: async (chatId) => {
        const chatIdNum = parseInt(chatId);
        if (!isNaN(chatIdNum)) {
          await loadAndRenderSidebar();
          switchChat(chatIdNum);
        }
      },
      createAgentChat,
      setActiveChat: (chatId) => {
        currentChatId = chatId;
        loadChatMessages(chatId);
      },
      sendMessage,
      switchChat,
      attachImage: (imageData) => {
        pendingImage = imageData;
      },
      clearPendingImage: () => {
        pendingImage = null;
      }
    };
    
    // Listen for UI events
    document.addEventListener('chatLoaded', (e) => {
      if (e.detail && e.detail.chatId) {
        switchChat(e.detail.chatId);
      }
    });
    
    // Trigger chat switch from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const chatId = urlParams.get('chat');
    if (chatId) {
      setTimeout(() => {
        window.chatManager.loadChatFromUrl(chatId);
      }, 1000);
    }
  }

  // Start initialization
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();