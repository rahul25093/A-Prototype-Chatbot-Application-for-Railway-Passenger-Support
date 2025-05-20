// script.js
const chatBody = document.querySelector(".chat-body");
const messageInput = document.querySelector(".message-input");
const fileInput = document.querySelector("#file-input");
const fileUploadWrapper = document.querySelector(".file-upload-wrapper");
const fileCancelButton = document.querySelector("#file-cancel");
const chatbotToggler = document.querySelector("#chatbot-toggler");
const closeChatbot = document.querySelector("#close-chatbot");
const chatForm = document.querySelector(".chat-form");
const messageInputArea = document.createElement("div");
messageInputArea.classList.add("message-input-area");

const API_KEY = "YOUR_GEMINI_API_KEY"; // IMPORTANT: Replace with your actual Gemini API Key
const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${API_KEY}`;
const RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook";
// const RASA_ACTION_URL = "http://localhost:5055/webhook"; // Uncomment if you use Rasa actions

const userData = {
    message: null,
    file: {
        data: null,
        mime_type: null
    }
};

const chatHistory = [];
let initialInputHeight = messageInput.scrollHeight;

const setupInputArea = () => {
    const controlsDiv = chatForm.querySelector(".chat-controls");
    const originalSendMessageButton = chatForm.querySelector("#send-message");

    messageInputArea.appendChild(messageInput);
    if (originalSendMessageButton) {
         messageInputArea.appendChild(originalSendMessageButton);
    }

    chatForm.insertBefore(messageInputArea, controlsDiv);
    initialInputHeight = messageInput.scrollHeight;
};
setupInputArea();

const sendMessageButton = document.querySelector("#send-message"); // Re-select after moving

const createMessageElement = (content, ...classes) => {
    const div = document.createElement("div");
    div.classList.add("message", ...classes);
    div.innerHTML = content;
    return div;
};

const formatTrainResponse = (text) => {
    if (!text) return ""; // Handle null or undefined text

    text = String(text); // Ensure text is a string

    if (text.includes("```") && (text.toLowerCase().includes("train") || text.toLowerCase().includes("pnr"))) {
        const codeBlockMatch = text.match(/```([\s\S]*?)```/);
        if (codeBlockMatch && codeBlockMatch[1]) {
            const tableContent = codeBlockMatch[1].trim();
            const lines = tableContent.split('\n');
            
            let htmlOutput = `<div class="train-info-header">Information</div>`;
            htmlOutput += `<div class="train-table-wrapper">`;
            htmlOutput += `<table class="train-table">`;
            
            if (lines.length > 0) {
                const headerParts = lines[0].split('|').map(part => part.trim()).filter(part => part);
                if (headerParts.length > 0) {
                    htmlOutput += `<thead><tr>`;
                    for (const part of headerParts) {
                        htmlOutput += `<th>${part}</th>`;
                    }
                    htmlOutput += `</tr></thead>`;
                }
                
                htmlOutput += `<tbody>`;
                const dataStartIndex = lines[1] && lines[1].match(/^[\s|:-]+$/) ? 2 : 1;

                for (let i = dataStartIndex; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (line) {
                        const rowParts = line.split('|').map(part => part.trim());
                        if (headerParts.length > 0 && rowParts.length === headerParts.length && rowParts.some(part => part)) {
                            htmlOutput += `<tr>`;
                            for (const part of rowParts) {
                                htmlOutput += `<td>${part}</td>`;
                            }
                            htmlOutput += `</tr>`;
                        } else if (rowParts.length === 1 && rowParts[0]) {
                             htmlOutput += `<tr><td colspan="${headerParts.length || 1}">${rowParts[0]}</td></tr>`;
                        }
                    }
                }
                 htmlOutput += `</tbody>`;
            }
            
            htmlOutput += `</table>`;
            htmlOutput += `</div>`;
            
            const beforeCodeBlock = text.split('```')[0].trim();
            const afterCodeBlock = text.split('```').slice(2).join('```').trim();
            
            let finalResponse = "";
            if (beforeCodeBlock) {
                finalResponse += `<div class="train-additional-info">${beforeCodeBlock.replace(/\n/g, '<br>')}</div>`;
            }
            finalResponse += htmlOutput;
            if (afterCodeBlock) {
                finalResponse += `<div class="train-additional-info">${afterCodeBlock.replace(/\n/g, '<br>')}</div>`;
            }
            
            return finalResponse;
        }
    }
    
    if (text.includes("🚆 Train | 📍 From | 🎯 To | ⏰ Timings | 📢 Status")) {
        const lines = text.split('\n');
        let htmlOutput = '';
        
        htmlOutput += `<div class="train-info-header">Train Information</div>`;
        htmlOutput += `<div class="train-table-wrapper">`;
        htmlOutput += `<table class="train-table">`;
        
        htmlOutput += `<thead><tr>
            <th>🚆 Train</th>
            <th>📍 From</th>
            <th>🎯 To</th>
            <th>⏰ Time</th>
            <th>📢 Status</th>
        </tr></thead>`;
        
        htmlOutput += `<tbody>`;
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line && !line.toLowerCase().startsWith('here') && !line.toLowerCase().startsWith('these')) {
                const parts = line.split(/\s*\|\s*/);
                if (parts.length >= 5) {
                    htmlOutput += `<tr>
                        <td>${parts[0].trim()}</td>
                        <td>${parts[1].trim()}</td>
                        <td>${parts[2].trim()}</td>
                        <td>${parts[3].trim()}</td>
                        <td>${parts[4].trim()}</td>
                    </tr>`;
                }
            }
        }
        htmlOutput += `</tbody>`;
        htmlOutput += `</table>`;
        htmlOutput += `</div>`;
        
        const additionalTextLines = lines.filter(line => 
            line.toLowerCase().startsWith('here') || 
            line.toLowerCase().startsWith('these') || 
            (line.includes('train') && !line.includes('🚆'))
        );
        if (additionalTextLines.length > 0) {
             htmlOutput += `<div class="train-additional-info">${additionalTextLines.join('<br>')}</div>`;
        }
        return htmlOutput;
    }
    
    const tempDiv = document.createElement('div');
    tempDiv.textContent = text;
    return tempDiv.innerHTML.replace(/\n/g, '<br>');
};

const generateBotResponse = async (incomingMessageDiv) => {
    const messageElement = incomingMessageDiv.querySelector(".message-text");
    
    chatHistory.push({
        role: "user",
        parts: [
            { text: userData.message }, 
            ...(userData.file.data ? [{ inline_data: userData.file }] : [])
        ]
    });

    const rasaRequestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            sender: "user123_frontend",
            message: userData.message
        })
    };

    try {
        incomingMessageDiv.classList.add("thinking");
        let apiResponseText = "";

        console.log("Sending to Rasa:", RASA_API_URL, JSON.stringify(rasaRequestOptions.body));
        const rasaResponse = await fetch(RASA_API_URL, rasaRequestOptions);
        
        if (rasaResponse.ok) {
            const rasaData = await rasaResponse.json();
            console.log("Rasa response data:", rasaData);
            
            if (rasaData && rasaData.length > 0) {
                apiResponseText = rasaData.map(msg => msg.text || "").join("\n").trim();
                rasaData.forEach(msg => {
                    if (msg.custom) {
                        if (msg.custom.type === "table_markdown" && msg.custom.data) {
                            apiResponseText += "\n```\n" + msg.custom.data + "\n```";
                        }
                    }
                });
            } else {
                apiResponseText = "I'm sorry, I didn't get a specific response from the server.";
            }
        } else {
            console.error("Rasa API error:", rasaResponse.status, await rasaResponse.text());
            apiResponseText = "Sorry, I'm having trouble connecting to my brain right now. Please try again later.";
        }
        
        if (apiResponseText) {
            const formattedResponse = formatTrainResponse(apiResponseText);
            messageElement.innerHTML = formattedResponse;
        } else {
            messageElement.innerText = "I'm not sure how to respond to that.";
        }

        chatHistory.push({
            role: "model",
            parts: [{ text: apiResponseText || "No clear response." }]
        });

    } catch (error) {
        console.error("Error in generateBotResponse:", error);
        if (messageElement) { // Check if messageElement is not null
            messageElement.classList.add("error");
            messageElement.innerText = "Oops! Something went wrong. Please try again.";
        }
    } finally {
        userData.file = { data: null, mime_type: null };
        fileUploadWrapper.classList.remove("file-uploaded");
        const imgPreview = fileUploadWrapper.querySelector("img");
        if (imgPreview) {
            imgPreview.src = "#";
        }

        if (incomingMessageDiv) { // Check if incomingMessageDiv is not null
            incomingMessageDiv.classList.remove("thinking");
        }
        chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth"});
    }
};

const handleOutgoingMessage = (e) => {
    userData.message = messageInput.value.trim();
    if (!userData.message && !userData.file.data) return;

    messageInput.value = "";
    messageInput.style.height = `${initialInputHeight}px`;

    const outgoingMessageDiv = createMessageElement("", "user-message");
    const textDiv = document.createElement('div');
    textDiv.classList.add('message-text');
    textDiv.textContent = userData.message;
    outgoingMessageDiv.appendChild(textDiv);

    if(userData.file.data) {
        const img = document.createElement('img');
        img.src = `data:${userData.file.mime_type};base64,${userData.file.data}`;
        img.classList.add('attachment');
        outgoingMessageDiv.appendChild(img);
    }
    
    chatBody.appendChild(outgoingMessageDiv);
    chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth"});

    setTimeout(() => {
        const thinkingMessageContent = `<svg class="bot-avatar" xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 2048 2048"><path fill="currentColor" d="M768 1024H640V896h128v128zm512 0h-128V896h128v128zm512-128v256h-128v320q0 40-15 75t-41 61t-61 41t-75 15h-264l-440 376v-376H448q-40 0-75-15t-61-41t-41-61t-15-75v-320H128V896h128V704q0-40 15-75t41-61t61-41t75-15h448V303q-29-17-46-47t-18-64q0-27 10-50t27-40t41-28t50-10q27 0 50 10t40 27t28 41t10 50q0 34-17 64t-47 47v209h448q40 0 75 15t61 41t41 61t15 75v192h128zm-256-192q0-26-19-45t-45-19H448q-26 0-45 19t-19 45v768q0 26 19 45t45 19h448v226l264-226h312q26 0 45-19t19-45V704zm-851 462q55 55 126 84t149 30q78 0 149-29t126-85l90 91q-73 73-167 112t-198 39q-103 0-197-39t-168-112l90-91z" /></svg>
                <div class="message-text">
                    <div class="thinking-indicator">
                        <div class="dot"></div><div class="dot"></div><div class="dot"></div>
                    </div>
                </div>`;
        const incomingMessageDiv = createMessageElement(thinkingMessageContent, "bot-message");
        chatBody.appendChild(incomingMessageDiv);
        chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth"});
        generateBotResponse(incomingMessageDiv);
    }, 600);
};

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault(); 
        if (messageInput.value.trim() !== "" || userData.file.data) {
            handleOutgoingMessage(e);
        }
    }
});

messageInput.addEventListener("input", () => {
    messageInput.style.height = `auto`;
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 100)}px`;
});

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if(!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const imgPreview = fileUploadWrapper.querySelector("img");
        if (imgPreview) {
            imgPreview.src = e.target.result;
        }
        fileUploadWrapper.classList.add("file-uploaded");
        const base64String = e.target.result.split(",")[1];

        userData.file = {
            data: base64String,
            mime_type: file.type
        };
        fileInput.value = "";
    };
    reader.readAsDataURL(file);
});

fileCancelButton.addEventListener("click", () => {
    userData.file = { data: null, mime_type: null };
    fileUploadWrapper.classList.remove("file-uploaded");
    const imgPreview = fileUploadWrapper.querySelector("img");
    if (imgPreview) {
        imgPreview.src = "#";
    }
});

const voiceAssistantButton = document.querySelector("#voice-assistant");
let isRecording = false;
let recognition = null;

const startSound = new Audio("https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3");
startSound.volume = 0.5;
const endSound = new Audio("https://assets.mixkit.co/active_storage/sfx/2571/2571-preview.mp3");
endSound.volume = 0.5;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isRecording = true;
        voiceAssistantButton.classList.add("recording");
        console.log("Voice recognition started.");
        startSound.play().catch(e => console.error("Error playing start sound:", e));
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        messageInput.value = transcript;
        messageInput.dispatchEvent(new Event("input"));
        
        setTimeout(() => {
            if (messageInput.value.trim() !== "") {
                const syntheticEvent = { preventDefault: () => {} };
                handleOutgoingMessage(syntheticEvent);
            }
        }, 200);
    }; // Added semicolon

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        if(event.error === 'no-speech') {
            alert("No speech was detected. Please try again.");
        } else if (event.error === 'audio-capture') {
            alert("No microphone was found. Ensure that a microphone is installed and that microphone settings are configured correctly.");
        } else if (event.error === 'not-allowed') {
            alert("Permission to use microphone was denied. Please enable it in your browser settings.");
        } else {
            alert("An error occurred during speech recognition: " + event.error);
        }
        // onend will be called implicitly by the browser after an error,
        // or if stop() is called.
    }; // Added semicolon

    recognition.onend = () => {
        console.log("Voice recognition ended.");
        // Play end sound only if it was genuinely recording and not stopped by onresult's logic immediately.
        // The main purpose of onend is cleanup.
        if (isRecording) { // Check if it was actually recording
            endSound.play().catch(e => console.error("Error playing end sound:", e));
        }
        isRecording = false;
        voiceAssistantButton.classList.remove("recording");
    }; // Added semicolon
} else {
    console.warn("Speech recognition not supported in this browser.");
    if (voiceAssistantButton) voiceAssistantButton.style.display = "none";
} // Added semicolon after the else block if it were a standalone statement, but it's fine here as it's the end of an if-else.

if (voiceAssistantButton) { // Check if button exists before adding listener
    voiceAssistantButton.addEventListener("click", () => {
        if (!recognition) {
            alert("Speech recognition is not supported in your browser.");
            return;
        }

        if (isRecording) {
            recognition.stop(); 
        } else {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(() => {
                    // startSound is played in onstart now
                    setTimeout(() => { // Slight delay can sometimes help
                        try {
                            recognition.start();
                        } catch (e) {
                            console.error("Could not start recognition:", e);
                            alert("Could not start voice recognition. It might be busy or an error occurred.");
                            isRecording = false; // Ensure state is reset
                            voiceAssistantButton.classList.remove("recording"); // Ensure UI is reset
                        }
                    }, 100); // Reduced delay, onstart handles sound
                })
                .catch(err => {
                    console.error("Microphone permission denied or error:", err);
                    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                        alert("Microphone permission denied. Please enable it in your browser settings to use voice input.");
                    } else {
                        alert("Could not access microphone. Please ensure it's connected and not in use by another application.");
                    }
                });
        }
    });
} // Semicolon might be expected by some linters after this block if it were the last statement, but it's fine.

if (sendMessageButton) {
    sendMessageButton.addEventListener("click", (e) => {
        e.preventDefault();
        if (messageInput.value.trim() !== "" || userData.file.data) {
            handleOutgoingMessage(e);
        }
    });
}

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    if (messageInput.value.trim() !== "" || userData.file.data) {
        handleOutgoingMessage(e);
    }
});

const fileUploadButton = document.querySelector("#file-upload");
if (fileUploadButton) {
    fileUploadButton.addEventListener("click", () => fileInput.click());
}
if (chatbotToggler) {
    chatbotToggler.addEventListener("click", () => document.body.classList.toggle("show-chatbot"));
}
if (closeChatbot) {
    closeChatbot.addEventListener("click", () => document.body.classList.remove("show-chatbot"));
}