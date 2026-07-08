const axios = require('axios');
const TwinSimulation = require('../models/TwinSimulation');
const FootprintLog = require('../models/FootprintLog');

const simulateCarbonTwin = async (req, res) => {
  try {
    const userId = req.user._id;
    const { buy_ev, install_solar, stop_flying, reduce_ac } = req.body;

    // Get user's latest footprint logs to pass to the Python AI service
    const logs = await FootprintLog.find({ user_id: userId }).sort({ date: -1 }).limit(20);
    const formattedLogs = logs.map(log => {
      const logObj = log.toObject();
      logObj._id = logObj._id.toString();
      logObj.user_id = logObj.user_id.toString();
      return logObj;
    });

    const aiServiceUrl = (process.env.AI_SERVICE_URL || 'http://127.0.0.1:8001').replace(/\/+$/, '');
    
    // Call Python AI microservice
    let aiResponse;
    try {
      aiResponse = await axios.post(`${aiServiceUrl}/ai/twin/simulate`, {
        toggles: { buy_ev, install_solar, stop_flying, reduce_ac },
        latest_logs: formattedLogs,
        profile: {
          country: req.user.profile?.country || 'US',
          diet_preference: req.user.profile?.diet_preference || 'omnivore',
          household_size: req.user.profile?.household_size || 1,
          has_car: req.user.profile?.has_car || false
        }
      });
    } catch (err) {
      console.error('Failed to call AI microservice for twin simulation:', err.message);
      return res.status(502).json({ detail: 'AI microservice is unavailable or returned an error.' });
    }

    const {
      original_co2_kg,
      projected_co2_kg,
      reduction_kg,
      reduction_pct,
      savings_usd_desc,
      lifestyle_impact,
      top_savings_sources,
      chart_data
    } = aiResponse.data;

    // Save simulation record to MongoDB
    const simulationRecord = new TwinSimulation({
      user_id: userId,
      simulated_at: new Date(),
      toggles: { buy_ev, install_solar, stop_flying, reduce_ac },
      results: {
        original_co2_kg,
        projected_co2_kg,
        reduction_kg,
        reduction_pct,
        savings_usd_desc,
        lifestyle_impact,
        top_savings_sources,
        chart_data
      }
    });

    const savedRecord = await simulationRecord.save();

    res.json({
      id: savedRecord._id.toString(),
      original_co2_kg,
      projected_co2_kg,
      reduction_kg,
      reduction_pct,
      savings_usd_desc,
      lifestyle_impact,
      top_savings_sources,
      chart_data
    });
  } catch (error) {
    console.error('Carbon twin simulation error:', error);
    res.status(500).json({ detail: 'Internal Server Error' });
  }
};

module.exports = {
  simulateCarbonTwin
};
