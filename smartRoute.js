import React, { useState } from 'react';
import * as XLSX from 'xlsx';
import { Loader2, MapPin, Truck, FileSpreadsheet, ArrowLeft } from 'lucide-react';

const ShipmentOptimizer = () => {
  const [shipments, setShipments] = useState([]);
  const [newShipment, setNewShipment] = useState({
    shipment_id: '',
    latitude: '',
    longitude: '',
    delivery_timeslot: ''
  });
  const [optimizedTrips, setOptimizedTrips] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mapUrl, setMapUrl] = useState(null);
  const [selectedTripId, setSelectedTripId] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewShipment(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    const reader = new FileReader();

    reader.onload = (event) => {
      const workbook = XLSX.read(event.target.result, { type: 'binary' });
      const sheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[sheetName];
      const data = XLSX.utils.sheet_to_json(worksheet);

      const formattedShipments = data.map(row => ({
        shipment_id: String(row['Shipment ID'] || row['shipment_id'] || `S${Math.random().toString(36).substr(2, 9)}`),
        latitude: parseFloat(row['Latitude'] || row['latitude']),
        longitude: parseFloat(row['Longitude'] || row['longitude']),
        delivery_timeslot: row['Delivery Timeslot'] || row['delivery_timeslot'] || '09:00-10:00'
      }));

      setShipments(prev => [...prev, ...formattedShipments]);
    };

    reader.readAsBinaryString(file);
  };

  const addShipment = () => {
    if (Object.values(newShipment).every(v => v.trim() !== '')) {
      setShipments(prev => [...prev, { ...newShipment }]);
      setNewShipment({
        shipment_id: '',
        latitude: '',
        longitude: '',
        delivery_timeslot: ''
      });
    }
  };

  const viewSingleTrip = async (tripId) => {
    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/map/${tripId}`);
      const mapHtml = await response.text();
      setMapUrl(`data:text/html;charset=utf-8,${encodeURIComponent(mapHtml)}`);
      setSelectedTripId(tripId);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const viewAllTrips = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/all-trips-map');
      const mapHtml = await response.text();
      setMapUrl(`data:text/html;charset=utf-8,${encodeURIComponent(mapHtml)}`);
      setSelectedTripId(null);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const optimizeRoutes = async () => {
    setIsLoading(true);
    try {
      const requestData = { shipments };
      
      const response = await fetch('http://localhost:8000/optimize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (response.ok) {
        const optimizedData = await response.json();
        setOptimizedTrips(optimizedData);
        await viewAllTrips();
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <style>
        {`
          .container {
            max-width: 1200px;
            margin: auto;
            padding: 20px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
          }
          .header {
            background: #1E293B;
            color: white;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          }
          .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
          }
          .input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
            margin-bottom: 10px;
          }
          .button {
            width: 100%;
            padding: 10px;
            background: #1E293B;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
          }
          .button:hover {
            background: #334155;
          }
          .optimize-btn {
            background: #064E3B;
          }
          .optimize-btn:hover {
            background: #065F46;
          }
          .back-btn {
            background: #374151;
            margin-bottom: 10px;
          }
          .back-btn:hover {
            background: #1F2937;
          }
          .shipment-list {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            border-radius: 5px;
            background: #f9f9f9;
          }
          .shipment-item {
            display: flex;
            justify-content: space-between;
            padding: 8px;
            border-bottom: 1px solid #ddd;
            cursor: pointer;
            transition: background 0.2s ease;
          }
          .shipment-item:hover {
            background: #f0f0f0;
          }
          .selected-trip {
            background: #E0E7FF;
          }
        `}
      </style>

      <div className="header">
        <div style={{ maxWidth: '1200px', margin: 'auto', maxHeight:'' }}>
          <h1 className="text-3xl font-bold flex items-center">
            <Truck className="mr-3" size={32} />
            Route Optimization Dashboard
          </h1>
          <p className="mt-2 text-gray-100">Optimize your delivery routes efficiently</p>
        </div>
      </div>

      <div className="container">
        <div className="card">
          <h2 className="text-xl font-bold mb-4 flex items-center">
            <Truck className="mr-2" /> Shipment Input
          </h2>

          <div className="mb-4">
            <label htmlFor="xlsx-upload" className="button flex items-center justify-center">
              <FileSpreadsheet className="mr-2" />
              Upload Excel Shipment File
              <input type="file" id="xlsx-upload" accept=".xlsx, .xls" className="hidden" onChange={handleFileUpload} />
            </label>
          </div>

          <div>
            <input name="shipment_id" placeholder="Shipment ID" className="input" value={newShipment.shipment_id} onChange={handleInputChange} />
            <input name="latitude" placeholder="Latitude" type="number" step="0.000001" className="input" value={newShipment.latitude} onChange={handleInputChange} />
            <input name="longitude" placeholder="Longitude" type="number" step="0.000001" className="input" value={newShipment.longitude} onChange={handleInputChange} />
            <input name="delivery_timeslot" placeholder="Delivery Timeslot (HH:MM-HH:MM)" className="input" value={newShipment.delivery_timeslot} onChange={handleInputChange} />
            <button onClick={addShipment} className="button">Add Shipment</button>
          </div>

          <div className="mt-4">
            <h3 className="font-bold mb-2">Shipments: {shipments.length}</h3>
            <div className="shipment-list">
              {shipments.map((s, index) => (
                <div key={index} className="shipment-item">
                  <span>{s.shipment_id}</span>
                  <span>{s.latitude}, {s.longitude}</span>
                  <span>{s.delivery_timeslot}</span>
                </div>
              ))}
            </div>
          </div>

          <button onClick={optimizeRoutes} disabled={shipments.length === 0 || isLoading} className="button optimize-btn mt-4">
            {isLoading ? <Loader2 className="mr-2 animate-spin" /> : 'Optimize Routes'}
          </button>
        </div>

        <div className="card">
          <h2 className="text-xl font-bold mb-4 flex items-center">
            <MapPin className="mr-2" /> Optimization Results
          </h2>

          {selectedTripId && (
            <button onClick={viewAllTrips} className="button back-btn flex items-center justify-center">
              <ArrowLeft className="mr-2" /> View All Trips
            </button>
          )}
          
          {mapUrl && <iframe src={mapUrl} width="100%" height="350px" title="Trip Map" />}

          {optimizedTrips && (
            <div className="mt-4">
              <h3 className="font-bold mb-2">Trip Details</h3>
              <div className="shipment-list">
                {optimizedTrips.map((trip, index) => (
                  <div 
                    key={index} 
                    className={`shipment-item ${selectedTripId === trip.TRIP_ID ? 'selected-trip' : ''}`}
                    onClick={() => viewSingleTrip(trip.TRIP_ID)}
                  >
                    <div>Trip ID: {trip.TRIP_ID}</div>
                    <div>Shipment: {trip.Shipment_ID}</div>
                    <div>Vehicle: {trip.Vehicle_Type}</div>
                    <div>Timeslot: {trip.TIME_SLOT}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default ShipmentOptimizer;