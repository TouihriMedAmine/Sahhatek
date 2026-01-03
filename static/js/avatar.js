/**
 * Avatar Web Component v1.0
 * 
 * A lightweight, modular 3D avatar component for web integration.
 * Built with Three.js.
 * 
 * Features:
 * - Dynamic color themes (for multi-agent support)
 * - Realistic mouth animation (2.0 Hz)
 * - Mouse-following eyes (prevented clipping at Z=2.2)
 * - Simple API for external control
 * 
 * Author: Senior Full-Stack Developer
 * Date: 2025-12-29
 */

class AvatarComponent {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`AvatarComponent: Canvas with ID '${canvasId}' not found.`);
            return;
        }

        // Configuration
        this.options = {
            backgroundColor: options.backgroundColor || 0xf8f9fa,
            defaultTheme: options.defaultTheme || 'neutral',
            autoBlink: options.autoBlink !== undefined ? options.autoBlink : true,
            mouseTracking: options.mouseTracking !== undefined ? options.mouseTracking : true
        };

        // Theme Definitions - Targeted for specific Agents
        this.themes = {
            // 1. Welcome / Pharmacist / Generalist
            welcome: { name: 'Welcome', gradient: this._generateGradient('clinical') },
            
            // 2. Medical QA (General Questions)
            medical_qa: { name: 'Medical QA', gradient: this._generateGradient('expert') },
            
            // 3. Triage (Emergency)
            triage: { name: 'Triage', gradient: this._generateGradient('alert') },
            
            // 4. Mental Health (Support)
            mental_health: { name: 'Mental Health', gradient: this._generateGradient('calm') },
            
            // 5. Rumor (Fact Checking)
            rumor: { name: 'Rumor', gradient: this._generateGradient('investigate') },
            
            // Fallback
            neutral: { name: 'Neutral', gradient: this._generateGradient('neutral') }
        };

        this.currentThemeName = this.options.defaultTheme || 'welcome';

        // State
        // State
        this.isSpeaking = false;
        this.speakTimer = 0;
        
        // Blink/Wink State
        this.blinkState = { leftTimer: 0, rightTimer: 0, isBlinkingLeft: false, isBlinkingRight: false };
        
        // Mood State
        this.currentMood = 'neutral';
        this.eyebrowTarget = { lRot: 0, rRot: 0, lY: 1.3, rY: 1.3 };
        this.mouthTarget = { curve: 1.0 }; // 1.0 = Smile
        this.currentMouthCurve = 1.0;
        
        this.time = 0;

        // Mouse Tracking State
        this.mouse = { x: 0, y: 0 };
        this.targetEye = { x: 0, y: 0 };
        this.currentEye = { x: 0, y: 0 };

        // Three.js Core
        this.scene = null;
        this.camera = null;
        this.renderer = null;

        // Avatar Parts
        this.head = null;
        this.eyesGroup = null;
        this.leftEye = null;
        this.rightEye = null;
        this.mouthGroup = null;
        this.mouthFill = null;
        this.mouthLine = null;

        // Natural blink tracking
        this.lastBlinkTime = 0;
        this.nextScheduledBlink = this._scheduleNextBlink();
        this.naturalBlinkProbability = options.naturalBlinkProbability || 0.25; // 25% default
        this.blinkOnSpeechStartProbability = 0.15; // 15% chance when starting speech


        this._init();
        this._animate();
        this._setupNaturalBlink();
    }


    /**
     * Trigger a natural blink during conversation
     * Called strategically during agent responses
     * Respects cooldown and probability
     */
    naturalBlink() {
        // Don't blink if we just blinked (cooldown: 1 second)
        if (Date.now() - this.lastBlinkTime < 1000) {
            console.log('👁️ Blink skipped (cooldown)');
            return;
        }
        
        // Probabilistic blink (default 25%)
        if (Math.random() < this.naturalBlinkProbability) {
            this.blink();
            this.lastBlinkTime = Date.now();
            console.log('👁️ Natural blink triggered (conversation)');
        } else {
            console.log('👁️ Natural blink skipped (probability)');
        }
    }

    // ==========================================
    // Public API
    // ==========================================

    /**
     * Start the talking animation
     */

    startSpeaking() {
        this.isSpeaking = true;
        this.speakTimer = 0;
        this.blinkOnSpeechStart(); // NEW: Occasional blink when starting

    }

    /**
     * Stop the talking animation
     */
    stopSpeaking() {
        this.isSpeaking = false;
        // Smooth transition handled in update loop
    }


    /**
     * Schedule next random blink (2-5 seconds from now)
     */
    _scheduleNextBlink() {
        return Date.now() + (2000 + Math.random() * 3000);
    }

    /**
     * Set up natural blinking interval
     * This creates the "idle" blinking behavior
     */
    _setupNaturalBlink() {
        if (!this.options.autoBlink) return;
        
        setInterval(() => {
            const now = Date.now();
            
            // Check if it's time for scheduled blink (only when not speaking)
            if (now >= this.nextScheduledBlink && !this.isSpeaking) {
                this.blink();
                this.nextScheduledBlink = this._scheduleNextBlink();
                console.log('⏰ Scheduled idle blink');
            }
        }, 500); // Check every 500ms
    }


    /**
     * Trigger a blink (both eyes)
     */
    blink() {
        this.blinkState.isBlinkingLeft = true;
        this.blinkState.isBlinkingRight = true;
        this.blinkState.leftTimer = 0;
        this.blinkState.rightTimer = 0;
    }

    /**
     * NEW: Blink when starting to speak (less frequent)
     * 15% probability
     */
    blinkOnSpeechStart() {
        if (Math.random() < this.blinkOnSpeechStartProbability) {
            this.blink();
            this.lastBlinkTime = Date.now();
            console.log('🗣️ Speech start blink');
        }
    }

    /**
     * Wink Left Eye
     */
    winkLeft() {
        this.blinkState.isBlinkingLeft = true;
        this.blinkState.leftTimer = 0;
    }

    /**
     * Wink Right Eye
     */
    winkRight() {
        this.blinkState.isBlinkingRight = true;
        this.blinkState.rightTimer = 0;
    }

    /**
     * Set Emotional Mood
     * @param {string} mood - 'neutral', 'happy', 'sad', 'serious', 'surprised'
     */
    setMood(mood) {
        this.currentMood = mood;
        console.log(`Mood set to: ${mood}`);

        let lRot = 0, rRot = 0, lY = 1.3, rY = 1.3;
        let curve = 1.0; 

        switch(mood) {
            case 'happy':
            case 'neutral': 
                // Default
                break;
            case 'sad': 
                // Eyebrows Outer Down (Inverted V approx) -> Rotate +
                lRot = -0.4; rRot = 0.4; 
                lY = 1.35; rY = 1.35;
                curve = -0.6; // Frown
                break;
            case 'serious': 
                // Eyebrows Inner Down (V shape) -> Rotate -
                lRot = 0.5; rRot = -0.5;
                lY = 1.25; rY = 1.25;
                curve = 0.0; // Flat
                break;
            case 'surprised':
                lRot = 0; rRot = 0;
                lY = 1.5; rY = 1.5;
                curve = 0.3; // Open circle approx logic handles open
                break;
        }
        
        this.eyebrowTarget = { lRot, rRot, lY, rY };
        this.mouthTarget = { curve };
    }

    /**
     * Set the avatar's color theme
     * @param {string} themeName - 'neutral', 'assistant', 'creative', 'nature', 'energetic', 'mystic'
     */
    setTheme(themeName) {
        if (!this.themes[themeName]) {
            console.warn(`AvatarComponent: Theme '${themeName}' not found. Using neutral.`);
            themeName = 'neutral';
        }

        if (this.currentThemeName === themeName) {
            console.log(`✅ Avatar already using theme: ${themeName}`);
            return;
        }

        console.log(`🎨 Avatar theme changing: ${this.currentThemeName} → ${themeName}`);
        this.currentThemeName = themeName;
        
        // Re-create head with new colors
        if (this.head) {
            this.scene.remove(this.head);
            this.head.geometry.dispose();
            this.head.material.dispose();
            this._createHead();
        }
        
        // Update Accessories
        this._updateAccessories(themeName);

        // NEW: Trigger a natural blink during theme change for "personality"
        setTimeout(() => {
            this.naturalBlink();
        }, 300);

        console.log(`✅ Avatar theme changed to: ${this.themes[themeName].name}`);
    }

    // ==========================================
    // Internal Initialization
    // ==========================================

    _init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.options.backgroundColor);

        // Camera
        const width = this.canvas.clientWidth;
        const height = this.canvas.clientHeight;
        const aspect = width / height;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
        this.camera.position.set(0, 0, 8); // Fixed frontal position

        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);

        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        this.scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(5, 5, 5);
        this.scene.add(dirLight);

        // Build Avatar
        this._createHead();
        this._createEyes();
        this._createEyebrows();
        this._createMouth();

        // Listeners
        if (this.options.mouseTracking) {
            this._setupMouseTracking();
        }
        window.addEventListener('resize', () => this._onResize());

        // Auto Blink Loop
        if (this.options.autoBlink) {
            setInterval(() => {
                if (!this.isBlinking && Math.random() > 0.4) this.blink();
            }, 3500);
        }

        // Initial Accessories
        this._updateAccessories(this.currentThemeName);

        // Click Listener for Mood Cycling
        this.canvas.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent propagation
            this.cycleMood();
        });
    }

    /**
     * Cycle through available moods
     */
    cycleMood() {
        const moods = ['neutral', 'happy', 'sad', 'serious', 'surprised'];
        const currentIndex = moods.indexOf(this.currentMood);
        const nextIndex = (currentIndex + 1) % moods.length;
        const nextMood = moods[nextIndex];
        
        this.setMood(nextMood);
        
        // Visual feedback
        this._showMoodNotification(nextMood);
    }

    _showMoodNotification(mood) {
        // Simple canvas overlay text or console log for now
        // Ideally we could use a DOM element if available
        console.log(`Mood switched to: ${mood}`);
        
        // Optional: Trigger a small animation like a blink
        this.blink();
    }

    // ==========================================
    // Geometry Creation
    // ==========================================

    _createHead() {
        const geometry = new THREE.SphereGeometry(2, 40, 40);
        
        // Get colors for current theme
        const themeColors = this.themes[this.currentThemeName].gradient;
        const colorAttribute = [];
        const positions = geometry.attributes.position;

        for (let i = 0; i < positions.count; i++) {
            const y = positions.getY(i);
            const t = (y + 2) / 4; // Normalize y (-2 to 2) to (0 to 1)
            
            // Map t to gradient array
            const colorIndex = Math.floor(Math.max(0, Math.min(1, t)) * (themeColors.length - 1));
            const c = themeColors[colorIndex];
            colorAttribute.push(c.r, c.g, c.b);
        }

        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colorAttribute, 3));
        
        const material = new THREE.MeshPhongMaterial({
            vertexColors: true,
            shininess: 30,
            flatShading: false
        });

        this.head = new THREE.Mesh(geometry, material);
        this.scene.add(this.head);
    }

    _createEyes() {
        this.eyesGroup = new THREE.Group();
        
        // Position eyes forward Z=2.2 to prevent clipping
        const eyeZ = 2.2; 
        
        this.leftEye = this._createSingleEye();
        this.leftEye.position.set(-0.6, 0.5, eyeZ);
        this.eyesGroup.add(this.leftEye);

        this.rightEye = this._createSingleEye();
        this.rightEye.position.set(0.6, 0.5, eyeZ);
        this.eyesGroup.add(this.rightEye);

        this.scene.add(this.eyesGroup);
    }

    _createSingleEye() {
        const group = new THREE.Group();

        // Sclera (White)
        const whiteGeo = new THREE.CircleGeometry(0.32, 32);
        const whiteMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const whiteMesh = new THREE.Mesh(whiteGeo, whiteMat);
        group.add(whiteMesh);

        // Pupil Container (for localized movement)
        const pupilContainer = new THREE.Group();
        
        // Pupil (Black)
        const pupilGeo = new THREE.CircleGeometry(0.16, 32);
        const pupilMat = new THREE.MeshBasicMaterial({ color: 0x111111 });
        const pupilMesh = new THREE.Mesh(pupilGeo, pupilMat);
        pupilMesh.position.z = 0.01; // Slightly above white
        
        pupilContainer.add(pupilMesh);
        group.add(pupilContainer);
        
        // Store reference to pupil container for animation
        group.userData.pupilContainer = pupilContainer;

        return group;
    }

    _createEyebrows() {
        const browMat = new THREE.MeshPhongMaterial({ color: 0x3e2723 });
        const browGeo = (THREE.CapsuleGeometry)
            ? new THREE.CapsuleGeometry(0.12, 0.7, 4, 8)
            : new THREE.BoxGeometry(0.7, 0.12, 0.12);

        this.leftEyebrow = new THREE.Mesh(browGeo, browMat);
        this.leftEyebrow.rotation.z = 1.57;
        this.leftEyebrow.position.set(-0.6, 1.3, 2.15);
        this.scene.add(this.leftEyebrow);

        this.rightEyebrow = new THREE.Mesh(browGeo, browMat);
        this.rightEyebrow.rotation.z = 1.57;
        this.rightEyebrow.position.set(0.6, 1.3, 2.15);
        this.scene.add(this.rightEyebrow);
    }

    _createMouth() {
        this.mouthGroup = new THREE.Group();
        const mouthZ = 2.21; // Just in front of eyes plane

        // 1. Smiling Line (Rest State)
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(-0.6, -0.8, 0),
            new THREE.Vector3(0, -1.0, 0),
            new THREE.Vector3(0.6, -0.8, 0)
        );
        const points = curve.getPoints(32);
        const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
        const lineMat = new THREE.LineBasicMaterial({ color: 0x3e2723, linewidth: 3 });
        this.mouthLine = new THREE.Line(lineGeo, lineMat);
        this.mouthLine.position.z = mouthZ;
        this.mouthGroup.add(this.mouthLine);

        // 2. Open Mouth Shape (Speaking State)
        const shape = new THREE.Shape();
        shape.moveTo(-0.6, 0);
        shape.quadraticCurveTo(0, -0.3, 0.6, 0); // Bottom curve
        shape.quadraticCurveTo(0, -0.1, -0.6, 0); // Top curve
        
        const shapeGeo = new THREE.ShapeGeometry(shape);
        const shapeMat = new THREE.MeshBasicMaterial({ 
            color: 0x3e2723, 
            transparent: true, 
            opacity: 0 
        });
        
        this.mouthFill = new THREE.Mesh(shapeGeo, shapeMat);
        this.mouthFill.position.set(0, -0.8, mouthZ + 0.01);
        this.mouthFill.scale.set(1, 0.1, 1); // Start closed
        
        this.mouthGroup.add(this.mouthFill);
        this.scene.add(this.mouthGroup);
    }

    // ==========================================
    // Gradients
    // ==========================================

    _generateGradient(type) {
        const colors = [];
        const steps = 40;
        
        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            let c = new THREE.Color();

            switch(type) {
                case 'clinical': // Welcome: Darker shades of white/blue-grey
                    // Starts light grey, fades to distinct blue-grey for visibility
                    c.setRGB(0.9 - t*0.1, 0.92 - t*0.05, 0.95); 
                    if (t > 0.5) c.setRGB(0.7, 0.75, 0.85 - t*0.1);
                    break;

                case 'expert': // Medical QA: Teal -> Surgical Green
                    c.setRGB(0.0 + t*0.2, 0.6 + t*0.1, 0.5 + t*0.2);
                    break;

                case 'alert': // Triage: Orange -> Red
                    c.setRGB(1.0, 0.6 - t*0.4, 0.2 + t*0.1);
                    break;

                case 'calm': // Mental Health: Pinkish/Rose (Warm, empathetic)
                    // Soft Pink to Rose
                    c.setRGB(1.0, 0.7 - t*0.2, 0.8 - t*0.1);
                    break;

                case 'investigate': // Rumor: Lighter Indigo/Lavender (Less dark)
                    // Brighter purple/blue mix, much lighter than before
                    c.setRGB(0.4 + t*0.2, 0.4 + t*0.2, 0.8 + t*0.1);
                    break;

                case 'neutral': 
                default: 
                    c.setRGB(0.9, 0.9, 0.9);
                    break;
            }
            colors.push(c);
        }
        return colors;
    }

    // ==========================================
    // Animation Loop
    // ==========================================

    _animate() {
        requestAnimationFrame(() => this._animate());

        const delta = 0.016; // Approx 60fps
        this.time += delta;

        this._updateEyes(delta);
        this._updateMouth(delta);
        this._updateBlink(delta);
        this._updateMood(delta); // New Mood Transition

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    _updateEyes(delta) {
        // Smooth Lerp for eye following
        const lerpSpeed = 5.0 * delta;
        this.currentEye.x += (this.targetEye.x - this.currentEye.x) * lerpSpeed;
        this.currentEye.y += (this.targetEye.y - this.currentEye.y) * lerpSpeed;

        if (this.leftEye && this.rightEye) {
            const lPupil = this.leftEye.userData.pupilContainer;
            const rPupil = this.rightEye.userData.pupilContainer;
            
            if (lPupil && rPupil) {
                lPupil.position.x = this.currentEye.x;
                lPupil.position.y = this.currentEye.y;
                rPupil.position.x = this.currentEye.x;
                rPupil.position.y = this.currentEye.y;
            }
        }
    }

    _updateMouth(delta) {
        if (this.isSpeaking) {
            this.speakTimer += delta;
            
            // 2.0 Hz Frequency - More natural speech rhythm
            const freq = 2.0;
            const wave = Math.sin(this.speakTimer * freq * Math.PI * 2);
            
            // Map -1..1 to 0..1 with bias towards opening
            const openAmount = Math.max(0, (wave + 0.2) / 1.2);

            if (this.mouthFill) {
                // Scale Y for realistic opening effect
                // Factor 2.5 makes the opening impactful
                
                // MOOD ADJUSTMENT:
                // If currentMouthCurve is negative (Sad), we want to invert the U shape to a n shape
                // We can do this by scaling Y negatively.
                // However, the anchor point is at the TOP of the shape (y=0 in local coords).
                // If we scale Y negative, it grows UPWARDS.
                // Our shape:
                // moveTo(-0.6, 0); quadraticCurveTo(0, -0.3, ...); (Goes down)
                // If scaled -1, it goes (0, 0.3).
                
                let moodScale = 1.0;
                if (this.currentMouthCurve < -0.1) moodScale = -1.0; // Invert for sad/angry

                const targetScale = (0.2 + openAmount * 2.5) * moodScale;
                this.mouthFill.scale.set(1, targetScale, 1);
                
                // Opacity
                this.mouthFill.material.opacity = 0.7 + openAmount * 0.3;
            }

            // Move the resting line slightly down (or up if sad)
            if (this.mouthLine) {
                 // Hide line more when speaking
                this.mouthLine.material.opacity = 0.3; 
                this.mouthLine.material.transparent = true;
            }

        } else {
            // Smooth close
            if (this.mouthFill) {
                this.mouthFill.material.opacity *= 0.85;
                this.mouthFill.scale.y = this.mouthFill.scale.y * 0.8 + 0.1;
                
                if (this.mouthFill.material.opacity < 0.05) {
                    this.mouthFill.material.opacity = 0;
                }
            }
            if (this.mouthLine) {
                this.mouthLine.position.y *= 0.85;
            }
        }
    }

    // ==========================================
    // Blink & Wink Logic
    // ==========================================

    blink() {
        this.blinkState.isBlinkingLeft = true;
        this.blinkState.isBlinkingRight = true;
        this.blinkState.leftTimer = 0;
        this.blinkState.rightTimer = 0;
    }

    winkLeft() {
        this.blinkState.isBlinkingLeft = true;
        this.blinkState.leftTimer = 0;
    }

    winkRight() {
        this.blinkState.isBlinkingRight = true;
        this.blinkState.rightTimer = 0;
    }

    _updateBlink(delta) {
        const duration = 0.15; // fast blink

        // Helper to calc scale
        const calcScale = (timer) => {
            const progress = timer / duration;
            if (progress < 0.5) return 1.0 - (progress * 2);
            if (progress < 1.0) return (progress - 0.5) * 2;
            return 1.0;
        };

        // Left Eye
        if (this.blinkState.isBlinkingLeft) {
            this.blinkState.leftTimer += delta;
            if (this.blinkState.leftTimer >= duration) {
                this.blinkState.isBlinkingLeft = false;
                if (this.leftEye) this.leftEye.scale.y = 1.0;
            } else {
                if (this.leftEye) this.leftEye.scale.y = calcScale(this.blinkState.leftTimer);
            }
        }

        // Right Eye
        if (this.blinkState.isBlinkingRight) {
            this.blinkState.rightTimer += delta;
            if (this.blinkState.rightTimer >= duration) {
                this.blinkState.isBlinkingRight = false;
                if (this.rightEye) this.rightEye.scale.y = 1.0;
            } else {
                if (this.rightEye) this.rightEye.scale.y = calcScale(this.blinkState.rightTimer);
            }
        }
    }

    // ==========================================
    // Mood & Expression Logic
    // ==========================================

    setMood(mood) {
        this.currentMood = mood;
        console.log(`Mood set to: ${mood}`);

        switch(mood) {
            case 'happy':
            case 'neutral': // Default Smile
                this.eyebrowTarget = { lRot: 0, rRot: 0, lY: 1.3, rY: 1.3 };
                this.mouthTarget = { curve: 1.0, y: -0.8 };
                break;
            case 'sad': 
                // Previous: Inner Down (Angry looking). Fix: Inner Up (Sad looking / \ )
                // Left: +Rot (Inner Up). Right: -Rot (Inner Up).
                this.eyebrowTarget = { lRot: 0.5, rRot: -0.5, lY: 1.35, rY: 1.35 };
                this.mouthTarget = { curve: -0.6, y: -0.9 };
                break;
            case 'serious': 
                // Previous: Inner Up (Sad looking). Fix: Inner Down (Angry/Serious looking \ / )
                this.eyebrowTarget = { lRot: -0.4, rRot: 0.4, lY: 1.25, rY: 1.25 };
                this.mouthTarget = { curve: 0.0, y: -0.8 };
                break;
            case 'surprised': // High eyebrows, Open mouth
                this.eyebrowTarget = { lRot: 0, rRot: 0, lY: 1.5, rY: 1.5 };
                this.mouthTarget = { curve: 0.5, y: -0.75 };
                break;
        }
    }

    _updateMood(delta) {
        const lerp = 4.0 * delta;

        // Eyebrows
        if (this.leftEyebrow) {
            // Z rotation
            // Base rotation is 1.57 (horizontal). +Rot rotates Outer UP (Sad/Surprised). -Rot rotates Inner Down (Angry)?
            // Creating rotation relative to center.
            // Let's assume Z rotation around center of capsule.
            
            // Left: +Rot = Outer Down / Inner Up (Sad). -Rot = Outer Up / Inner Down (Angry)
            // Wait, standard rotation Z:
            // 0 is vertical. 1.57 is Horizontal (-).
            // +0.2 from 1.57 tip goes Down-Right. 
            
            // Let's simply Lerp rotation.z
            // Neutral: 1.57
            // Sad (Outer Down): 1.57 + 0.3
            // Serious (Inner Down): 1.57 - 0.3
            
            // Mapping from my setMood logic:
            // Happy: 0 -> 1.57
            // Sad: -0.4 -> 1.57 - 0.4 = 1.17 (Correct? Outer down?)
            // Let's just try and see.
            
            const baseRot = 1.57;
            
            this.leftEyebrow.rotation.z += ( (baseRot + this.eyebrowTarget.lRot) - this.leftEyebrow.rotation.z ) * lerp;
            this.leftEyebrow.position.y += ( this.eyebrowTarget.lY - this.leftEyebrow.position.y ) * lerp;
        
            this.rightEyebrow.rotation.z += ( (baseRot + this.eyebrowTarget.rRot) - this.rightEyebrow.rotation.z ) * lerp;
            this.rightEyebrow.position.y += ( this.eyebrowTarget.rY - this.rightEyebrow.position.y ) * lerp;
        }

        // Mouth Curve
        // Modifying quadratic bezier point 1 (Control Point)
        if (this.mouthLine) {
            // Rebuild geometry if curve changes significantly? 
            // Better: Just move the vertices of the BufferGeometry if possible, 
            // OR simpler: Flip rotation of the mouth group? No.
            // Re-generating geometry is expensive every frame.
            // MorphTarget is best but standard geo...
            // Let's just scale Y? -1 Scale Y inverts the curve!
            // Yes! Scale Y = curve value.
            
            // But wait, the shape is not symmetric around Y=0 of the object?
            // The quadratic curve goes from -0.8 to -1.0 to -0.8.
            // Center is Y=-0.8 approx.
            // If I scale Y, it might drift.
            
            // Let's try simple Scale Y modification on the Mouth Container Group.
            // The mouth is in `this.mouthGroup`. 
            // Center of mouth is roughly (0, -0.8).
            // If I scale -1, it flips around (0,0,0) of the Group (which is 0,0,0 of scene). Bad.
            
            // Solution: Modify the middle vertex of the line geometry.
            const positions = this.mouthLine.geometry.attributes.position;
            // 32 points. Middle is ~16.
            // Bezier curve is mathematically defined.
            // We can just update the 32 points based on current curve value.
            
            // To be efficient, only do every few frames or if diff is large.
            // But JS is fast. Let's strictly interpolate a "CurveFactor" variable.
            
            if (!this.currentMouthCurve) this.currentMouthCurve = 1.0;
            this.currentMouthCurve += (this.mouthTarget.curve - this.currentMouthCurve) * lerp;
            
            // Re-calc points
            const curve = new THREE.QuadraticBezierCurve3(
                new THREE.Vector3(-0.6, 0, 0),
                new THREE.Vector3(0, -0.2 * this.currentMouthCurve, 0), // Control point moves up/down
                new THREE.Vector3(0.6, 0, 0)
            );
            const points = curve.getPoints(32);
            // Update position attribute
            for(let i=0; i<points.length; i++) {
                positions.setXY(i, points[i].x, points[i].y + this.mouthTarget.y + 0.8); // Offset
                 // Manual offset adjustment to keep it at y=-0.8 roughly
                 // If curve is positive (smile), control point is below (-0.2).
                 // relative to 0.
            }
            // Actually, let's keep it simple.
            // Control Point Y = -0.2 * curve.
            // Anchor Points Y = 0.
            // Result is local to mouth. We add world offset Y.
            
            for(let i=0; i<points.length; i++) {
               positions.setXYZ(i, points[i].x, points[i].y - 0.8, 0); // -0.8 is base height
            }
            
            positions.needsUpdate = true;
        }
    }

    // ==========================================
    // Event Handlers
    // ==========================================

    _setupMouseTracking() {
        // Track mouse globally on the window
        window.addEventListener('mousemove', (e) => {
            if (!this.renderer) return;

            // Get canvas position relative to viewport
            const rect = this.canvas.getBoundingClientRect();
            
            // Calculate center of the avatar
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            // Calculate vector from center to mouse
            const dx = e.clientX - centerX;
            const dy = e.clientY - centerY;

            // Normalize based on window dimensions to limit range
            // We use a larger divisor to make the movement subtle but continuous
            // max rotation usually happens when mouse is at screen edge
            const x = dx / (window.innerWidth / 1.5); 
            const y = -dy / (window.innerHeight / 1.5);

            // Clamp values to prevent eyes rolling too far back
            // Max bounds: -1 to 1 for the logic, but we scale it down for the eyes
            this.targetEye.x = Math.max(-1, Math.min(1, x)) * 0.15; 
            this.targetEye.y = Math.max(-1, Math.min(1, y)) * 0.15;
        });
        
        // Remove mouseleave since we track window now
    }

    _onResize() {
        if (!this.camera || !this.renderer) return;

        const width = this.canvas.clientWidth;
        const height = this.canvas.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    // ==========================================
    // Accessories System
    // ==========================================

    _updateAccessories(themeName) {
        // Clear existing accessories
        if (this.accessoriesGroup) {
            this.scene.remove(this.accessoriesGroup);
            this.accessoriesGroup = null;
        }
        
        this.accessoriesGroup = new THREE.Group();
        this.scene.add(this.accessoriesGroup);

        switch(themeName) {
            case 'welcome':
                this._addNurseCap();
                break;
            case 'medical_qa':
                this._addStethoscope(); 
                break;
            case 'triage':
                this._addHeadset();
                this._addSquareGlasses();
                break;
            case 'mental_health':
                this._addGlasses(); // Restore Round Glasses
                this._addMustache(); // Keep Mustache
                break;
            case 'rumor':
                this._addMonocle();
                break;
        }
    }

    // ==========================================
    // Specific Accessories
    // ==========================================

    // Vests removed as per user request


    _addSquareGlasses() {
        // Thick Rimmed Square Glasses for Triage
        const glassesGroup = new THREE.Group();
        const frameMat = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
        
        // Square shape function
        const createSquareLens = (x) => {
            // Box frame with hole? Easier to use RingGeometry with 4 segments (diamond) rotated 45deg 
            // OR outline using tubes. Let's use 4 tubes for a proper square.
            
            const g = new THREE.Group();
            g.position.set(x, 0.4, 2.3); // Moved z forward to 2.3
            
            const w = 0.5;
            const h = 0.4;
            const t = 0.05; // thickness

            // Top
            const top = new THREE.Mesh(new THREE.BoxGeometry(w, t, t), frameMat);
            top.position.y = h/2;
            g.add(top);
            // Bottom
            const bot = new THREE.Mesh(new THREE.BoxGeometry(w, t, t), frameMat);
            bot.position.y = -h/2;
            g.add(bot);
            // Left
            const left = new THREE.Mesh(new THREE.BoxGeometry(t, h, t), frameMat);
            left.position.x = -w/2;
            g.add(left);
            // Right
            const right = new THREE.Mesh(new THREE.BoxGeometry(t, h, t), frameMat);
            right.position.x = w/2;
            g.add(right);

            // Glass
            const glass = new THREE.Mesh(new THREE.PlaneGeometry(w-0.05, h-0.05), new THREE.MeshPhongMaterial({
                color: 0xccffff, opacity: 0.3, transparent: true, shininess: 90
            }));
            glass.position.z = 0.01;
            g.add(glass);

            return g;
        };

        glassesGroup.add(createSquareLens(-0.65));
        glassesGroup.add(createSquareLens(0.65));

        // Bridge
        const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.05, 0.05), frameMat);
        bridge.position.set(0, 0.4, 2.3);
        glassesGroup.add(bridge);

        this.accessoriesGroup.add(glassesGroup);
    }

    _addMustache() {
        const mustacheGroup = new THREE.Group();
        const hairMat = new THREE.MeshBasicMaterial({ color: 0x5d4037 });
        const geo = (THREE.CapsuleGeometry)
            ? new THREE.CapsuleGeometry(0.12, 0.5, 4, 8)
            : new THREE.BoxGeometry(0.5, 0.12, 0.12);

        const p1 = new THREE.Mesh(geo, hairMat);
        p1.rotation.z = 1.3;
        p1.position.set(-0.35, -0.55, 2.3);
        mustacheGroup.add(p1);

        const p2 = new THREE.Mesh(geo, hairMat);
        p2.rotation.z = -1.3;
        p2.position.set(0.35, -0.55, 2.3);
        mustacheGroup.add(p2);

        this.accessoriesGroup.add(mustacheGroup);
    }

    _addNurseCap() {
        const capGroup = new THREE.Group();
        
        // Main Cap body
        const capGeo = new THREE.CylinderGeometry(0.85, 0.95, 0.5, 32);
        const capMat = new THREE.MeshPhongMaterial({ 
            color: 0xeceff1, // Off-white, slightly darker for visibility against pure white bg
            shininess: 10
        }); 
        const cap = new THREE.Mesh(capGeo, capMat);
        cap.position.y = 1.9;
        cap.rotation.x = -0.2;
        capGroup.add(cap);

        // Contrast Band
        const bandGeo = new THREE.CylinderGeometry(0.96, 0.96, 0.1, 32);
        const bandMat = new THREE.MeshBasicMaterial({ color: 0x90caf9 }); // Distinct Blue
        const band = new THREE.Mesh(bandGeo, bandMat);
        band.position.y = 1.7; 
        band.rotation.x = -0.2;
        capGroup.add(band);

        // Logo Placeholder Plane
        const logoGeo = new THREE.PlaneGeometry(0.4, 0.4);
        const logoMat = new THREE.MeshBasicMaterial({ 
            color: 0xffffff, 
            transparent: true,
            // map: new THREE.TextureLoader().load('path/to/logo.png') // TODO: Add Logo Here
        });
        const logo = new THREE.Mesh(logoGeo, logoMat);
        logo.position.set(0, 1.9, 0.55); // Front of cap
        logo.rotation.x = -0.2;
        capGroup.add(logo);

        // Default "Cross" logo fallback (if no image)
        const vBar = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.3, 0.01), new THREE.MeshBasicMaterial({color: 0xe74c3c}));
        vBar.position.z = 0.01;
        logo.add(vBar);
        const hBar = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.1, 0.01), new THREE.MeshBasicMaterial({color: 0xe74c3c}));
        hBar.position.z = 0.01;
        logo.add(hBar);

        this.accessoriesGroup.add(capGroup);
    }

    _addStethoscope() {
        // Stethoscope around the "neck" (bottom of sphere)
        const stethGroup = new THREE.Group();

        // 1. Tubing around neck (Torus)
        const tubeColor = 0x34495e; // Dark Blue/Grey tubing
        const tubeMat = new THREE.MeshPhongMaterial({ color: tubeColor });
        
        // We place it low, around y = -1.2
        const neckGeo = new THREE.TorusGeometry(1.6, 0.12, 16, 40, 4.5); // Partial arc
        const neckTube = new THREE.Mesh(neckGeo, tubeMat);
        neckTube.rotation.x = 1.6; // Flat
        neckTube.rotation.z = -2.25; // Center the opening at back
        neckTube.position.y = -1.2;
        stethGroup.add(neckTube);

        // 2. Connector piece (center chest)
        const centerGeo = new THREE.CylinderGeometry(0.15, 0.15, 0.3);
        const center = new THREE.Mesh(centerGeo, tubeMat);
        center.position.set(0, -1.2, 1.6);
        center.rotation.x = 0.5;
        stethGroup.add(center);

        // 3. Tube going down to chest piece involves a curve, simpler to use cylinders
        // Small tube hanging down
        const hangGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.6);
        const hang = new THREE.Mesh(hangGeo, tubeMat);
        hang.position.set(0, -1.6, 1.7);
        hang.rotation.x = 0.2;
        stethGroup.add(hang);

        // 4. The Chest Piece (Disc)
        const discGeo = new THREE.CylinderGeometry(0.4, 0.4, 0.1, 32);
        const discMat = new THREE.MeshPhongMaterial({ 
            color: 0xbdc3c7, // Silver
            shininess: 80 
        });
        const disc = new THREE.Mesh(discGeo, discMat);
        disc.rotation.x = 1.57; // Face forward
        disc.position.set(0, -1.9, 1.8);
        stethGroup.add(disc);

        this.accessoriesGroup.add(stethGroup);
    }

    _addHeadset() {
        // Headset for Triage - Improved connection
        const micGroup = new THREE.Group();
        const plasticMat = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });

        // Earpiece (Side)
        const earGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.2, 32);
        const ear = new THREE.Mesh(earGeo, plasticMat);
        ear.rotation.z = 1.57;
        ear.position.set(1.9, 0, 0); 
        micGroup.add(ear);

        // Headband
        const bandGeo = new THREE.TorusGeometry(2.0, 0.06, 16, 60, Math.PI);
        const band = new THREE.Mesh(bandGeo, plasticMat);
        micGroup.add(band);

        // Boom Arm Base (Connection to ear)
        const baseGeo = new THREE.SphereGeometry(0.2);
        const base = new THREE.Mesh(baseGeo, plasticMat);
        base.position.set(1.5, -0.2, 0.8); // Slightly forward from ear
        micGroup.add(base);

        // Connection Line (Ear to Boom Base)
        const lineGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.8);
        const line = new THREE.Mesh(lineGeo, plasticMat);
        line.position.set(1.7, -0.1, 0.4);
        line.rotation.x = 1.57;
        line.rotation.z = -0.5;
        micGroup.add(line);

        // Boom Arm
        const boomGeo = new THREE.CylinderGeometry(0.03, 0.03, 1.2);
        const boom = new THREE.Mesh(boomGeo, plasticMat);
        boom.position.set(1.0, -0.6, 1.4);
        boom.rotation.z = 1.2;
        boom.rotation.y = -0.5;
        micGroup.add(boom);

        // Mic Tip (Foam)
        const tipGeo = (THREE.CapsuleGeometry)
            ? new THREE.CapsuleGeometry(0.12, 0.25, 4, 8)
            : new THREE.SphereGeometry(0.18, 16, 16);
        const tipMat = new THREE.MeshBasicMaterial({ color: 0x1a1a1a });
        const tip = new THREE.Mesh(tipGeo, tipMat);
        tip.rotation.z = 1.57;
        tip.position.set(0.5, -0.9, 1.8);
        micGroup.add(tip);

        this.accessoriesGroup.add(micGroup);
    }

    _addGlasses() {
        // Mental Health - Sleek Reading Glasses
        const glassesGroup = new THREE.Group();
        const frameMat = new THREE.MeshPhongMaterial({ 
            color: 0x2c3e50, // Dark matte
            shininess: 30
        });
        
        // Thinner rims, slightly larger
        const lensRadius = 0.55;
        const lensGeo = new THREE.TorusGeometry(lensRadius, 0.04, 16, 48);
        
        // Left
        const left = new THREE.Mesh(lensGeo, frameMat);
        left.position.set(-0.65, 0.3, 2.15);
        glassesGroup.add(left);

        // Right
        const right = new THREE.Mesh(lensGeo, frameMat);
        right.position.set(0.65, 0.3, 2.15);
        glassesGroup.add(right);

        // Bridge - Arched
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(-0.3, 0.3, 2.15),
            new THREE.Vector3(0, 0.45, 2.15),
            new THREE.Vector3(0.3, 0.3, 2.15)
        );
        const points = curve.getPoints(10);
        const bridgeGeo = new THREE.BufferGeometry().setFromPoints(points);
        const bridgeMat = new THREE.LineBasicMaterial({ color: 0x2c3e50, linewidth: 3 });
        const bridge = new THREE.Line(bridgeGeo, bridgeMat);
        glassesGroup.add(bridge);

        // Glass Lenses (Transparent) - Adds realism
        const glassGeo = new THREE.CircleGeometry(lensRadius - 0.02, 32);
        const glassMat = new THREE.MeshPhongMaterial({
            color: 0xffffff,
            opacity: 0.2,
            transparent: true,
            shininess: 90
        });
        const leftGlass = new THREE.Mesh(glassGeo, glassMat);
        leftGlass.position.set(-0.65, 0.3, 2.15);
        glassesGroup.add(leftGlass);

        const rightGlass = new THREE.Mesh(glassGeo, glassMat);
        rightGlass.position.set(0.65, 0.3, 2.15);
        glassesGroup.add(rightGlass);

        this.accessoriesGroup.add(glassesGroup);
    }

    _addMonocle() {
        // Rumor Agent - High Visibility Monocle
        const monocleGroup = new THREE.Group();
        
        // Much thicker Gold Frame for visibility
        const frameMat = new THREE.MeshPhongMaterial({ 
            color: 0xffd700, // Gold
            shininess: 150,
            emissive: 0x443300 // Slight glow
        }); 
        
        // Frame
        const ringGeo = new THREE.TorusGeometry(0.65, 0.08, 16, 50);
        const ring = new THREE.Mesh(ringGeo, frameMat);
        ring.position.set(0.6, 0.5, 2.25);
        monocleGroup.add(ring);

        // Lens - Distinct color (Light Blue)
        const glassGeo = new THREE.CircleGeometry(0.6, 32);
        const glassMat = new THREE.MeshPhongMaterial({ 
            color: 0x81ecec, 
            opacity: 0.4, 
            transparent: true,
            shininess: 100
        });
        const glass = new THREE.Mesh(glassGeo, glassMat);
        glass.position.set(0.6, 0.5, 2.25);
        monocleGroup.add(glass);

        // Chain - Thicker and more visible
        const chainGeo = new THREE.CylinderGeometry(0.04, 0.04, 1.4);
        const chain = new THREE.Mesh(chainGeo, frameMat);
        chain.position.set(1.2, -0.2, 2.0);
        chain.rotation.z = 0.8;
        monocleGroup.add(chain);

        this.accessoriesGroup.add(monocleGroup);
    }
}
