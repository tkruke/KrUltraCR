// KrUltraAdmin.vue
// Torgeir Kruke

// Template inneholder HTML-koden som definerer hvordan komponenten skal se ut
<template>

  <div id="app" style="background-color: white;">
    
    <header>
      <img :src="LogoImage" alt="Logo" class="logo">
      <h1 class="header-title">KrUltra ADMIN</h1>
      <div class="clock">{{ currentDateTime }}</div>
    </header>

    <div class="error-monitor">
      # missing TS: {{ countCorrectedTimestamps() }} |
      # invalid: {{ countInvalidRegistrations() }}
    </div>

    <div class="toolbar">
      <div class="left-icons">
    
      <button @click="toggleUpdates" class="toolbar-button">
        <img v-if="isUpdating" :src="require('@/assets/Pause.png')" alt="Pause">
        <img v-else :src="require('@/assets/Play.png')" alt="Play">
      </button>
    
      <label for="viewModeSelect" class="toolbar-label">View:</label>
      <select id="viewModeSelect" class="toolbar-select" v-model="viewMode" @change="handleViewModeChange">
        <option value="auto">Automatic</option>
        <option value="detail">List</option>
        <option value="summary">Summary</option>
      </select>

      <button @click="toggleView" class="toolbar-button">
        <img :src="buttonImage" alt="Bytt visning">
      </button>
     
      <label for="raceSelector" class="toolbar-label" v-if="showGrouped && sortedGroupedData && sortedGroupedData.length">Choose race:</label>
      <select id="raceSelector" class="race-dropdown" v-if="showGrouped && sortedGroupedData && sortedGroupedData.length" v-model="selectedRace">
        <option v-for="race in uniqueRaces" :key="race">{{ race }}</option>
      </select>
    </div>

    <div class="info-icon-container">
      <img :src="InfoImage" alt="Info" class="info-icon" @mouseover="showTooltip = true" @mouseout="showTooltip = false">
      <div v-if="showTooltip" class="tooltip" v-html="tooltipText"></div>
    </div>
  </div>
      
    <section v-if="loading">
      <p>Loading...</p>
    </section>

    <section v-if="error">
      <p>{{ error }}</p>
    </section>


    <section v-if="showGrouped && sortedGroupedData && sortedGroupedData.length"> 
      
      <table>
        <thead>
          <tr>
            <th>Bib</th>
            <th>Name</th>
            <th>Race</th>
            <th v-for="checkpoint in uniqueCheckpoints" :key="checkpoint">{{ checkpoint }}</th>
            <th>Last reg.</th>
            <th>Tag uid</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(registration, index) in sortedGroupedData" :key="index" :class="{
              'highlight-error': shouldHighlightSumRow(registration.checkpoints),
            }">
            <td>{{ registration.bib }}</td>
            <td>{{ getRunnerName(registration.rfids[0]) }}</td>
            <td>{{ getRunnerRace(registration.rfids[0]) }}</td>
            <template v-if="Array.isArray(uniqueCheckpoints)">
              <td v-for="checkpoint in uniqueCheckpoints" :key="checkpoint">
                {{ registration.checkpoints ? (registration.checkpoints[checkpoint] || '0') : '0' }}
              </td>
            </template>
            <td>{{ formatDate(registration.timestamp, registration.reg_delay_ms) }}</td>
            <td v-html="registration.rfids.join('<br/>')"></td>
          </tr>
        </tbody>
      </table>
    </section>

    <table v-else-if="!showGrouped && data && Object.keys(data).length">
      <thead>
        <tr>
          <th>#</th>
          <th>Key</th>
          <th>Bib</th>
          <th>Name</th>
          <th>Race</th>
          <th>CP</th>
          <th>Timestamp</th>
          <th>Tag uid</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>

        <!-- <tr v-for="(registration, index) in sortedData" :key="index" :class="{  -->
        <tr v-for="(registration, index) in sortedData" :key="registration.key" :class="{ 
            'highlight-error': registration.status === 'missing timestamp auto-corrected',
            'invalid-row': registration.status === 'invalid',
          }" >
          <td>{{ sortedData.length - index }}</td>
          <td>{{ registration.key }}</td>
          <td>{{ getRunnerBib(registration.rfid_tag_uid) }}</td>
          <td>{{ getRunnerName(registration.rfid_tag_uid) }}</td>
          <td>{{ getRunnerRace(registration.rfid_tag_uid) }}</td>
          <td>{{ getCheckpointInfo(registration.rfid_reader_id).checkpoint }}</td>
          <!-- <td>{{ getCheckpointInfo(registration.rfid_reader_id).cp_description }}</td> -->
          <td>{{ formatDate(registration.timestamp, registration.reg_delay_ms) }}</td>
          <td>{{ registration.rfid_tag_uid }}</td>
          <td>{{ registration.status }}</td>
        </tr>
      </tbody>

    </table>

    <section v-else>
      <p>Ingen data tilgjengelig</p>
    </section>
  </div>
</template>

  
<script>
// Inneholder JavaScript-koden som styrer komponentens logikk.

// import
import { auth, db, signInWithEmail } from "@/firebaseInit.js";
// import { signInAnonymously } from "firebase/auth";
import { onValue, ref as dbRef } from "firebase/database";
import { get, set, update } from "firebase/database";
import ListImage from '@/assets/List.png';
import SumImage from '@/assets/Sum.png';
import AutoImage from '@/assets/Auto.png';
import InfoImage from '@/assets/Info.png';
import logoImage from '@/assets/logo.png';


export default {    // Eksporterer komponenten slik at den kan brukes i andre filer.
  name: "KrultraAdmin",   // Brukes for å referere til komponenten i andre filer. 

  // data
  data() {    // data() returnerer et objekt som inneholder data som brukes i komponenten.
    return {
      loading: true,
      data: null,
      stopListening: null,
      isUpdating: true,
      viewMode: 'auto',
      autoTimer: null,

      // isDetailedView: true,
      showGrouped: false,
      error: null,
      runners: null,
      rfidReaders: null,
      selectedRace: 'All',
      currentDateTime: '',
      autoDelay: 5000,          // 5 seconds delay before switching to summary view
      highlightPeriod: 300000, // 60000 per minute, 300000 per 5 minutes
      InfoImage: InfoImage,
      showTooltip: false,
      tooltipText: process.env.VUE_APP_TOOLTIP_TEXT.replace(/\\n/g, '<br>'),
      LogoImage: logoImage,
    };
  },

  // Computed
  computed: {   // Computed properties er funksjoner som returnerer data som kan brukes i komponenten.
    highestTimestampRow() {
      return Math.max(...this.sortedGroupedData.map(row => row.timestamp - row.reg_delay_ms));
    },

    buttonImage() {
      if (this.viewMode === 'auto') {
        return AutoImage;
      } else if (this.viewMode === 'detail') {
        return ListImage;
      } else {
        return SumImage;
      }
    },

    uniqueCheckpoints() {
      const checkpoints = [];
      if (this.rfidReaders) {
        Object.values(this.rfidReaders)
          .filter(reader => reader.status === 1)
          .forEach(reader => {
            checkpoints.push({ name: reader.checkpoint, id: reader.checkpoint_id });
          });
      }
      const sortedCheckpoints = checkpoints.sort((a, b) => a.id - b.id).map(cp => cp.name);
      this.logToFirebase(`sortedCheckpoints: ${JSON.stringify(sortedCheckpoints)}`);
      return sortedCheckpoints;
    },


    prettyData() {
      if (this.data === null) {
        return "";
      }
      return JSON.stringify(this.data, null, 2);
    },


    groupedData() {
      const result = {};
      if (this.data && this.rfidReaders) {
        Object.values(this.data).forEach(registration => {
          const rfid = registration.rfid_tag_uid;
          const reader = this.rfidReaders[registration.rfid_reader_id];
          const checkpoint = reader ? reader.checkpoint : "Ukjent";
          const bib = this.getRunnerBib(rfid);
          const race = this.getRunnerRace(rfid);

          if ((this.selectedRace !== 'All' && race !== this.selectedRace) || registration.status === 'invalid') {
            return;
          }

          if (!result[bib]) {
            result[bib] = {
              count: 0,
              checkpoints: {},
              bib: bib,
              timestamp: 0,
              reg_delay_ms: 0,
              rfids: []
            };
          }
          result[bib].count += 1;
          result[bib].checkpoints[checkpoint] = (result[bib].checkpoints[checkpoint] || 0) + 1;


          // Oppdater timestamp og reg_delay_ms
          if (registration.timestamp - registration.reg_delay_ms > result[bib].timestamp - result[bib].reg_delay_ms) {
            result[bib].timestamp = registration.timestamp;
            result[bib].reg_delay_ms = registration.reg_delay_ms;
          }

          if (rfid && !result[bib].rfids.includes(rfid)) {
            result[bib].rfids.push(rfid);
          }
        });
      }
      return result;
    },

    // funksjon for å returnere grupperte og sorterte data. Kan utvides til å ta hensyn til brukervalg for sorteringsrekkefølge.
    sortedGroupedData() {
      const groupedData = this.groupedData;
      const uniqueCheckpoints = this.uniqueCheckpoints;

      const sortedArray = Object.entries(groupedData).sort((a, b) => {
        for (const checkpoint of uniqueCheckpoints) {
          const countA = a[1].checkpoints[checkpoint] || 0;
          const countB = b[1].checkpoints[checkpoint] || 0;
          const diff = countB - countA;
          if (diff !== 0) {
            return diff;
          }
        }
        // Hvis alle sjekkpunktene har likt antall, sorter etter laveste timestamp
        return a[1].timestamp - b[1].timestamp;
      });

      return sortedArray.map(([bib, data]) => ({ bib, ...data }));
    },

    // funksjon for å returnere "All" + alle unike race_name fra runners
    uniqueRaces() {
      const races = new Set();
      Object.values(this.runners).forEach(runner => {
        races.add(runner.race_name);
      });
      return ["All", ...Array.from(races)];
    },

    // funksjon for å returnere sortert data. Kan utvides til å ta hensyn til brukervalg for sorteringsrekkefølge.
    // sortedData() {
    //   return Object.values(this.data).sort((a, b) => b.timestamp - a.timestamp);
    // },
    sortedData() {
      return Object.entries(this.data)
        .sort(([, a], [, b]) => b.timestamp - a.timestamp)
        .map(([key, registration]) => ({ key, ...registration }));
    },

    currentTime() {
      return new Date().toLocaleTimeString();
    }

  },


  // Methods
  methods: {    // Metoder som brukes i komponenten. Inneholder funksjoner som kan kalles fra komponentens template.
    logAndReturn(value) {
      console.log("Value:", value);
      return value;
    },

    shouldHighlight(adjustedTimestamp) {
      const currentTime = Date.now(); // Nåværende tid i millisekunder
      return currentTime - adjustedTimestamp <= this.highlightPeriod; // Endret innenfor de siste x sekundene, hvor x er angitt av this.highlightPeriod
    },

    shouldHighlightSumRow(checkpoints) {
      const checkpointValues = this.uniqueCheckpoints.map(cp => checkpoints[cp] || 0);
      let dropCount = 0; // Teller for antall ganger det er et "dropp" på 1 registrering

      for (let i = 0; i < checkpointValues.length - 1; i++) {
        const diff = checkpointValues[i] - checkpointValues[i + 1];

        if (diff === 1) {
          dropCount++;
        } else if (diff !== 0) {
          return true; // Marker raden hvis forskjellen er noe annet enn 0 eller 1
        }
      }

      // Marker raden hvis det er mer enn ett "dropp" på 1 registrering
      return dropCount > 1;
    },

    updateDateTime() {
      const now = new Date();
      const day = String(now.getDate()).padStart(2, '0');
      const month = String(now.getMonth() + 1).padStart(2, '0'); // Måneder er 0-indeksert
      const year = now.getFullYear();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');

      this.currentDateTime = `${day}.${month}.${year} ${hours}:${minutes}:${seconds}`;
    },

    newRegistration() {
      if (this.viewMode === 'auto') {
        this.switchToDetail();
      }
    },

    switchToDetail() {
      this.showGrouped = false;
      if (this.autoTimer) {
        clearTimeout(this.autoTimer);
      }
      this.autoTimer = setTimeout(() => {
        this.showGrouped = true;
      }, this.autoDelay);
    },

    toggleUpdates() {
      if (this.isUpdating) {
        if (this.stopListening) {
          this.stopListening();
        }
        this.isUpdating = false;
        this.logToFirebase("Updates paused");
      } else {
        const registrationsRef = dbRef(db, "registrations");
        this.stopListening = onValue(registrationsRef, snapshot => {
          this.data = snapshot.val();
          this.loading = false;
        });
        this.isUpdating = true;
        this.logToFirebase("Updates resumed");
      }
    },

    formatDate(timestamp, reg_delay_ms = 0) {
      const adjustedTimestamp = timestamp - reg_delay_ms;
      const date = new Date(adjustedTimestamp);
      return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
    },

    toggleView() {
      // Nullstill timeren hvis den eksisterer
      if (this.autoTimer) {
        clearTimeout(this.autoTimer);
      }

      this.showGrouped = !this.showGrouped;

      if (this.viewMode === 'auto') {
        this.viewMode = 'detail';
        this.showGrouped = false;
      } else if (this.viewMode === 'detail') {
        this.viewMode = 'summary';
        this.showGrouped = true;
      } else {
        this.viewMode = 'auto';
        // Start timeren igjen hvis vi går tilbake til 'auto' modus
        this.switchToDetail();
      }

      console.log("viewMode:", this.viewMode);
    },

    handleViewModeChange() {
      // Her kan du legge til ytterligere logikk hvis nødvendig når viewMode endres
      console.log("View mode changed to:", this.viewMode);
      // toggleView();
      if (this.viewMode === 'auto') {
        this.switchToDetail();
      } else if (this.viewMode === 'detail') {
        this.showGrouped = false;
        if (this.autoTimer) {
          clearTimeout(this.autoTimer);
        }
      } else {  // this.viewMode === 'summary'
        this.showGrouped = true;
      }
    },

    async fetchRunners() {
      const runnersRef = dbRef(db, "runners");
      const snapshot = await get(runnersRef);
      this.runners = snapshot.val();
    },

    getRunnerName(rfid_tag_uid) {
      const runner = this.runners ? this.runners[rfid_tag_uid] : null;
      return runner ? `${runner.participant_first_name} ${runner.participant_last_name}` : "Ukjent";
    },

    getRunnerBib(rfid_tag_uid) {
      const runner = this.runners ? this.runners[rfid_tag_uid] : null;
      return runner ? runner.participant_bib : "Ukjent";
    },

    getRunnerRace(rfid_tag_uid) {
      const runner = this.runners ? this.runners[rfid_tag_uid] : null;
      return runner ? runner.race_name : "Ukjent";
    },

    async fetchRfidReaders() {
      const rfidReadersRef = dbRef(db, "rfid_readers");
      const snapshot = await get(rfidReadersRef);
      this.rfidReaders = snapshot.val();
    },

    getCheckpointInfo(rfid_reader_id) {
      const reader = this.rfidReaders ? this.rfidReaders[rfid_reader_id] : null;
      return reader ? { checkpoint: reader.checkpoint, cp_description: reader.cp_description } : { checkpoint: "Ukjent", cp_description: "Ukjent" };
    },

    async loginToFirebase() {
    try {
      await signInWithEmail(auth,
        process.env.VUE_APP_FIREBASE_EMAIL,
        process.env.VUE_APP_FIREBASE_PASSWORD
      );
      this.logToFirebase("Logged in successfully");
    } catch (error) {
      this.logToFirebase("Error logging in: " + error.message, "error");
    }
    },

    logToFirebase(message, type="log") {
      const uniqueKey = Date.now().toString(); // Bruker nåværende tidsstempel som en unik nøkkel
      const logRef = dbRef(db, 'logs/' + uniqueKey);
      set(logRef, {
        timestamp: Date.now(),
        type: type,
        message: message
      });
      if (type === "error") {
        console.error(message);
      } else if (type === "warning") {
        console.warn(message);
      } else if (type === "info") {
        console.info(message);
      } else if (type === "debug") {
        console.debug(message);
      } else {
        console.log(message);
      }
    },

    countCorrectedTimestamps() {
      if (!this.data) return 0;  // Returner 0 hvis data er undefined eller null
      return Object.values(this.data).filter(registration => registration.status === 'missing timestamp auto-corrected').length;
    },

    countInvalidRegistrations() {
      if (!this.data) return 0;  // Returner 0 hvis data er undefined eller null
      return Object.values(this.data).filter(registration => registration.status === 'invalid').length;
    }

  },  // methods


  // Lifecycle hooks - Som mounted(), created(), etc., for å kjøre kode på bestemte tidspunkter i komponentens livssyklus.
  async mounted() {   // mounted() kjøres når komponenten er ferdig montert i DOMen.
    try {
      // await signInAnonymously(auth);
      this.loginToFirebase();
      await this.fetchRunners();  // for å hente "runners" data
      await this.fetchRfidReaders();  // for å hente "rfid_readers" data

      this.updateDateTime();
      setInterval(this.updateDateTime, 1000);

      const registrationsRef = dbRef(db, "registrations");
      this.stopListening = onValue(registrationsRef, snapshot => {
        this.data = snapshot.val();
        if (this.data) {
        Object.entries(this.data).forEach(async ([key, registration]) => {
          if (!registration.timestamp) {
            const registrationRef = dbRef(db, "registrations/" + key);
            if (!registration.status) {
              // Dette er en ny registrering, sett status til 'registered'
              registration.discoveredAt = Date.now(); // Legg til en lokal discoveredAt timestamp
              try {
                await update(registrationRef, { 
                  status: 'registered',
                  discoveredAt: Date.now()
                });

                // Sett en timeout for å sjekke etter 10 sekunder om timestamp er på plass
                setTimeout(async () => {
                  const snapshot = await get(registrationRef);
                  const updatedRegistration = snapshot.val();
                  if (updatedRegistration.status === 'registered' && !updatedRegistration.timestamp) {
                    // Oppdater timestamp og status
                    await update(registrationRef, {
                      timestamp: Date.now() - 1000,
                      status: 'missing timestamp auto-corrected'
                    });
                  } else if (updatedRegistration.status === 'registered'){
                    await update(registrationRef, {
                      status: 'OK'
                    });
                  }
                }, 3000);

              } catch (error) {
                this.logToFirebase("Error updating registration status:" + error, "error");
              }
            } else {
              if (registration.discoveredAt) {
                registration.timestamp = registration.discoveredAt; // Sett timestamp lokalt for visning i tabellen
              } else {
                registration.timestamp = 1000; 
              }
            }
          }
        });

        }
        if (this.data === null) {
          this.error = "Ingen data tilgjengelig";
        }
        this.newRegistration();
        this.loading = false;
      }, error => {
        // Dette callbacket håndterer feil
        this.error = "En feil oppstod ved henting av data: " + error.message;
        this.loading = false;
      });
    } catch (error) {
      this.logToFirebase("Error signing in:" + error, "error");
      this.loading = false;
    }
  },


  beforeUnmount() {   // beforeUnmount() kjøres før komponenten blir avmontert fra DOMen.
    this.logToFirebase("beforeUnmount is being executed!");
    if (this.stopListening !== null) {
      this.stopListening();
    }
  },

};
</script>


// style - Inneholder CSS for å style komponenten. Kan være "scoped" for å begrense stilen til bare denne komponenten.
<style>
h1 {
  margin: 40px 0 0;
  colour: #42b983;
}

h3 {
  margin: 40px 0 0;
}

ul {
  list-style-type: none;
  padding: 0;
}

li {
  display: inline-block;
  margin: 0 10px;
}

a {
  color: #42b983;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border: 1px solid black;
  padding: 8px;
  text-align: left;
}

th {
  background-color: #f2f2f2;
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  text-align: center;
  color: #2c3e50;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f7f9fa;
  padding: 10px;
}

.logo {
  height: 50px;
}

.header-title {
  margin: 0;
  flex-grow: 1;
  text-align: center;
}

.clock {
  font-size: 1.2em;
}

.error-monitor {
  background-color: #ffcccc;
  color: #990000;
  padding: 5px;
  margin: 0px;
  margin-bottom: 5px;
  margin-right: 10px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  background-color: #1e80ba;
  padding: 5px;
}

.left-icons {
  display: flex;
  align-items: center;
}

.padded-button {
  padding: 0px 10px;
}

.header-title, .clock {
  color: #ba581e;
}

.toolbar-button, .info-icon {
  background: #1e80ba;
  border: none;
  padding: 0px 0px;
  margin: 0px;
  cursor: pointer;
  height: 30px;
  margin-right: 10px;
}

.toolbar-button img {
  height: 30px;
}

.race-dropdown {
  background-color: #1e80ba;
  color: white;
  border: 2px solid white;
  border-radius: 5px;
  padding: 5px;
  margin: 0px;
  cursor: pointer;
}

.highlight {
  background-color: #e9f2f8; /* lys blå farge */
}

.highest-timestamp {
  background-color: #fcebb6 !important;   /* lys gul farge */
}

.highlight-error {
  background-color: #FFD6D6; /* lys rød farge */
}

.invalid-row {
    background-color: lightgray;
    text-decoration: line-through;
}

.info-icon-container {
  position: relative;
  cursor: pointer;
}

/* .info-icon {
  height: 30px;
  padding: 5px;
  margin: 0px;
  margin-left: auto;
  cursor: pointer;
} */

.tooltip {
  position: absolute;
  background-color: #ffffff;
  padding: 5px;
  border: 2px solid black;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.5);
  left: -300px;
  max-width: 300px;
  display: inline-block;
  top: 100%;
}

.tooltip-text {
  visibility: hidden;
  position: absolute;
  right: 0;
  background-color: #c5ddf8;
  border: 1px solid #ccc;
  padding: 10px;
  width: 300px;
  z-index: 1000;
}

.tooltip-text.visible {
  visibility: visible;
  border: 2px solid black;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.5);
}

.info-icon-container:hover .tooltip-text {
  visibility: visible;
}

.toolbar-label {
  font-weight: bold;
  margin-right: 10px;
  color: white;
}

.toolbar-select {
  padding: 5px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  margin-right: 10px;
}

</style>
  