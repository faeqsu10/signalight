import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

export async function GET() {
  try {
    const scriptPath = path.join(process.cwd(), '../scripts/get_bigtech_data.py');
    const venvPython = path.join(process.cwd(), '../.venv/bin/python');
    
    const { stdout } = await execAsync(`${venvPython} ${scriptPath}`);
    const data = JSON.parse(stdout);
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching big tech data:', error);
    return NextResponse.json({ error: 'Failed to fetch data' }, { status: 500 });
  }
}
